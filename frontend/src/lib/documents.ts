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
  return fetchWithAuth(`/documents/chunks/${chunkId}/context`)
}
