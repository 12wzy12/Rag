import { consumeSse } from '@/utils/sse'

import type {
  ChatDoneEvent,
  ChatRefusedEvent,
  ChatSourcesEvent,
} from '@/types'

/** 与后端 /chat SSE 事件一一对应的处理器。 */
export interface ChatHandlers {
  onSources?: (data: ChatSourcesEvent) => void
  onChunk?: (text: string) => void
  onDone?: (data: ChatDoneEvent) => void
  onRefused?: (data: ChatRefusedEvent) => void
  onError?: (message: string) => void
}

const API_BASE = (import.meta.env.VITE_API_URL ?? '/api').replace(/\/$/, '')

/**
 * 对知识库发起流式问答（POST + SSE）。
 *
 * 事件序列见后端 chat.py：sources → chunk* → done；
 * 拒答时 refused → done；异常时 error（无 done）。
 * @param signal 用于“停止生成”（中断即取消底层读取）。
 */
export async function streamChat(
  kbId: number,
  payload: { query: string; sessionId?: number; topK?: number },
  handlers: ChatHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const body: Record<string, unknown> = { query: payload.query }
  if (payload.sessionId) body.session_id = payload.sessionId
  if (payload.topK) body.top_k = payload.topK

  const response = await fetch(`${API_BASE}/knowledge-bases/${kbId}/chat/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })

  await consumeSse(
    response,
    (event, data) => {
      const typed = data as Record<string, unknown>
      switch (event) {
        case 'sources':
          handlers.onSources?.(typed as unknown as ChatSourcesEvent)
          break
        case 'chunk':
          handlers.onChunk?.(String(typed.text ?? ''))
          break
        case 'done':
          handlers.onDone?.(typed as unknown as ChatDoneEvent)
          break
        case 'refused':
          handlers.onRefused?.(typed as unknown as ChatRefusedEvent)
          break
        case 'error':
          handlers.onError?.(String(typed.message ?? '未知错误'))
          break
        default:
          break
      }
    },
    signal,
  )
}
