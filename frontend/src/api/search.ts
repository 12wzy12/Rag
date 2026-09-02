import { http } from './client'

import type { SearchResult } from '@/types'

/** 对知识库执行多阶段语义检索（召回 → 重排 → 相关性判定）。 */
export async function searchDocuments(
  kbId: number,
  params: { query: string; topK?: number },
): Promise<SearchResult> {
  const body: Record<string, unknown> = { query: params.query }
  if (params.topK) body.top_k = params.topK
  const { data } = await http.post<SearchResult>(
    `/knowledge-bases/${kbId}/search`,
    body,
  )
  return data
}
