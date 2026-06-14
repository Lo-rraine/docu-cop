import { fetchWithAuth } from './http'

export interface ChunkDetail {
  chunk_id: string
  text: string
  ticker: string
  filing_type: string
  filing_year: number
  heading: string | null
  chunk_index: number
}

export interface ChunkContext {
  chunk: ChunkDetail
  prev: ChunkDetail | null
  next: ChunkDetail | null
}

export async function getChunkContext(chunkId: string): Promise<ChunkContext> {
  const { env } = await import('./env')
  const response = await fetchWithAuth(`${env.apiBaseUrl}/documents/chunks/${chunkId}/context`)
  if (!response.ok) {
    throw new Error(`Failed to fetch chunk context: ${response.status}`)
  }
  return response.json()
}
