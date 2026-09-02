import { http } from './client'

import type { ChatSession } from '@/types'

/** 某知识库下的全部会话（按时间倒序）。 */
export async function listSessions(kbId: number): Promise<ChatSession[]> {
  const { data } = await http.get<ChatSession[]>('/sessions', {
    params: { kb: kbId },
  })
  return data
}

export async function createSession(payload: {
  kb: number
  title?: string
}): Promise<ChatSession> {
  const { data } = await http.post<ChatSession>('/sessions', payload)
  return data
}

export async function deleteSession(id: number): Promise<void> {
  await http.delete(`/sessions/${id}`)
}

export interface MessagesPayload {
  session: ChatSession
  count: number
  messages: import('@/types').ChatMessage[]
}

/** 某个会话的完整历史（含每条 assistant 消息的知识来源）。 */
export async function listMessages(sessionId: number): Promise<MessagesPayload> {
  const { data } = await http.get<MessagesPayload>(`/sessions/${sessionId}/messages`)
  return data
}
