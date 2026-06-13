import { env } from './env'

export interface ChatMessage {
  id?: string
  role: 'user' | 'assistant'
  content: string
}

export interface StreamEvent {
  type: 'text' | 'data' | 'error' | 'done'
  data: string | Record<string, unknown>
}

export async function* streamChat(
  threadId: string,
  messages: ChatMessage[],
  signal?: AbortSignal
): AsyncGenerator<StreamEvent> {
  const response = await fetch(`${env.apiBaseUrl}/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify({
      id: threadId,
      messages: messages.map((m) => ({ role: m.role, content: m.content })),
    }),
    signal,
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
    yield {
      type: 'error',
      data: error.detail || `HTTP ${response.status}`,
    }
    return
  }

  if (!response.body) {
    yield {
      type: 'error',
      data: 'No response body',
    }
    return
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines[lines.length - 1]

      for (let i = 0; i < lines.length - 1; i++) {
        const line = lines[i].trim()
        if (!line) continue

        const event = parseStreamLine(line)
        if (event) yield event
      }
    }

    buffer += decoder.decode() // Flush remaining data
    const lines = buffer.split('\n')
    for (const line of lines) {
      const trimmed = line.trim()
      if (trimmed) {
        const event = parseStreamLine(trimmed)
        if (event) yield event
      }
    }
  } finally {
    reader.releaseLock()
  }

  yield { type: 'done', data: '' }
}

function parseStreamLine(line: string): StreamEvent | null {
  if (!line) return null

  // AI SDK format: 0:"token" | d:{json} | e:"error"
  const prefix = line[0]
  const content = line.slice(2) // Remove prefix and colon

  if (prefix === '0') {
    // Text token (message code 0)
    try {
      const text = JSON.parse(content)
      return { type: 'text', data: text }
    } catch {
      return { type: 'text', data: content }
    }
  } else if (prefix === 'd') {
    // Data part
    try {
      const data = JSON.parse(content)
      return { type: 'data', data }
    } catch {
      return null
    }
  } else if (prefix === 'e') {
    // Error
    try {
      const error = JSON.parse(content)
      return { type: 'error', data: error }
    } catch {
      return { type: 'error', data: content }
    }
  }

  return null
}
