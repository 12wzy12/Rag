import { http } from './client'

import type { KnowledgeBase } from '@/types'

/** 拉取全部知识库（含文档数 / 文本块数）。 */
export async function listKnowledgeBases(): Promise<KnowledgeBase[]> {
  const { data } = await http.get<KnowledgeBase[]>('/knowledge-bases')
  return data
}

export async function createKnowledgeBase(payload: {
  name: string
  description?: string
}): Promise<KnowledgeBase> {
  const { data } = await http.post<KnowledgeBase>('/knowledge-bases', payload)
  return data
}

export async function deleteKnowledgeBase(id: number): Promise<void> {
  await http.delete(`/knowledge-bases/${id}`)
}

export interface SearchParams {
  query: string
  topK?: number
}
