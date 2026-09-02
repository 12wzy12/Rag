import { defineStore } from 'pinia'
import { ref } from 'vue'

import * as api from '@/api/chat'
import * as sessionApi from '@/api/sessions'
import { getErrorMessage } from '@/api/client'

import type { ChatSourcesEvent, ChatSession, SearchChunk } from '@/types'

/**
 * 渲染用消息的结构化形状：同时容纳后端持久化消息（带 id/created_at）
 * 与流式中尚未落库的临时消息（assistant 带 streaming 标记）。
 * 后端返回的 ChatMessage 天然可赋值给该接口（多出的字段无妨）。
 */
interface ViewMessage {
  id?: number
  session: number
  role: 'user' | 'assistant'
  content: string
  sources: SearchChunk[]
  streaming?: boolean
  refused?: boolean
  error?: string
}

export const useChatStore = defineStore('chat', () => {
  const sessions = ref<ChatSession[]>([])
  const sessionsLoading = ref(false)
  const activeSessionId = ref<number | null>(null)
  const messages = ref<ViewMessage[]>([])
  const streaming = ref(false)
  const error = ref<string | null>(null)
  const kbId = ref<number | null>(null)

  let controller: AbortController | null = null

  const activeSession = (): ChatSession | null =>
    sessions.value.find((s) => s.id === activeSessionId.value) ?? null

  async function fetchSessions(targetKbId: number) {
    kbId.value = targetKbId
    sessionsLoading.value = true
    try {
      sessions.value = await sessionApi.listSessions(targetKbId)
    } finally {
      sessionsLoading.value = false
    }
  }

  async function selectSession(id: number) {
    activeSessionId.value = id
    error.value = null
    messages.value = []
    try {
      const payload = await sessionApi.listMessages(id)
      messages.value = payload.messages
    } catch (err) {
      error.value = getErrorMessage(err)
    }
  }

  async function createSession() {
    if (!kbId.value) return
    try {
      const session = await sessionApi.createSession({ kb: kbId.value })
      sessions.value = [session, ...sessions.value]
      await selectSession(session.id)
    } catch (err) {
      error.value = getErrorMessage(err)
    }
  }

  async function removeSession(id: number) {
    await sessionApi.deleteSession(id)
    sessions.value = sessions.value.filter((s) => s.id !== id)
    if (activeSessionId.value === id) {
      activeSessionId.value = null
      messages.value = []
    }
  }

  /** 发送一条消息并流式接收回答。无活动会话时自动新建。 */
  async function sendMessage(text: string) {
    const query = text.trim()
    if (!query || streaming.value || !kbId.value) return

    if (activeSessionId.value === null) {
      try {
        const session = await sessionApi.createSession({
          kb: kbId.value,
          title: query.slice(0, 30),
        })
        sessions.value = [session, ...sessions.value]
        activeSessionId.value = session.id
        messages.value = []
      } catch (err) {
        error.value = getErrorMessage(err)
        return
      }
    }

    const sessionId = activeSessionId.value
    messages.value.push({
      session: sessionId,
      role: 'user',
      content: query,
      sources: [],
    })

    const assistant: ViewMessage = {
      session: sessionId,
      role: 'assistant',
      content: '',
      sources: [],
      streaming: true,
      refused: false,
    }
    messages.value.push(assistant)
    error.value = null
    streaming.value = true

    controller = new AbortController()
    const signal = controller.signal

    const reconcile = async () => {
      try {
        const payload = await sessionApi.listMessages(sessionId)
        messages.value = payload.messages
      } catch {
        // 历史刷新失败时保留本地累积内容。
      }
    }

    const onSources = (data: ChatSourcesEvent) => {
      assistant.sources = data.results
      assistant.refused = data.refused
    }
    const onChunk = (piece: string) => {
      assistant.content += piece
    }
    const onDone = async () => {
      streaming.value = false
      await reconcile()
      await fetchSessions(kbId.value!) // 标题/会话列表与后端同步
    }
    const onRefused = (data: { message: string }) => {
      assistant.content = data.message
      assistant.refused = true
    }
    const onError = (message: string) => {
      error.value = message
      assistant.error = message
    }

    try {
      await api.streamChat(
        kbId.value,
        { query, sessionId },
        { onSources, onChunk, onDone, onRefused, onError },
        signal,
      )
    } catch (err) {
      if (!signal.aborted) {
        error.value = getErrorMessage(err)
        assistant.error = getErrorMessage(err)
      }
    } finally {
      assistant.streaming = false
      streaming.value = false
      controller = null
      if (signal.aborted) {
        // 用户停止生成：后端已尽力保存部分内容，重新拉取对齐。
        await reconcile()
      }
    }
  }

  function stop() {
    controller?.abort()
  }

  return {
    sessions,
    sessionsLoading,
    activeSessionId,
    activeSession,
    messages,
    streaming,
    error,
    fetchSessions,
    selectSession,
    createSession,
    removeSession,
    sendMessage,
    stop,
  }
})
