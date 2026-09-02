import { http } from './client'

import type { SearchParams, SearchResult } from '@/types'

/** 对知识库执行语义检索。 */
export async function searchDocuments(params: SearchParams): Promise<SearchResult> {
  const { data } = await http.post<SearchResult>('/search', params)
  return data
}
