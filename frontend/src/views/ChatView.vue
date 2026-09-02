<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'

import ChatInput from '@/components/chat/ChatInput.vue'
import ChatMessageItem from '@/components/chat/ChatMessageItem.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import KbSelector from '@/components/kb/KbSelector.vue'
import SessionList from '@/components/chat/SessionList.vue'
import { useChatStore } from '@/stores/chat'
import { useKbStore } from '@/stores/kb'

const chatStore = useChatStore()
const kbStore = useKbStore()

const scrollRef = ref<HTMLElement | null>(null)

async function syncKb() {
  const kbId = kbStore.currentKbId
  if (kbId == null) return
  await chatStore.fetchSessions(kbId)
  // 自动选中最近一次会话，让历史对话可继续追问。
  if (chatStore.sessions.length && chatStore.activeSessionId == null) {
    await chatStore.selectSession(chatStore.sessions[0].id)
  }
}

onMounted(async () => {
  if (!kbStore.items.length) {
    await kbStore.fetchKnowledgeBases()
  }
  await syncKb()
})

watch(
  () => kbStore.currentKbId,
  async (id) => {
    if (id == null) return
    await chatStore.fetchSessions(id)
    if (chatStore.sessions.length) {
      await chatStore.selectSession(chatStore.sessions[0].id)
    } else {
      chatStore.messages = []
    }
  },
)

// 新消息 / 流式追加 / 消息替换时自动滚动到底部。
watch(
  [
    () => chatStore.messages.length,
    () => chatStore.streaming,
    () => {
      const last = chatStore.messages[chatStore.messages.length - 1]
      return last ? last.content.length : 0
    },
  ],
  async () => {
    await nextTick()
    const el = scrollRef.value
    if (el) el.scrollTop = el.scrollHeight
  },
)

async function removeSession(id: number, title: string) {
  if (!window.confirm(`删除会话「${title}」？其中的问答记录将一并删除。`)) return
  try {
    await chatStore.removeSession(id)
  } catch {
    window.alert('删除失败，请稍后重试')
  }
}
</script>

<template>
  <div class="chat-view">
    <header class="chat-header">
      <div>
        <h1 class="chat-title">智能问答</h1>
        <p class="chat-subtitle">
          RAG 多阶段检索 + 流式生成：回答基于知识库内容，并标注可追溯的来源引用。
        </p>
      </div>
      <KbSelector v-if="kbStore.items.length" />
    </header>

    <EmptyState
      v-if="!kbStore.items.length"
      icon="📚"
      title="请先创建知识库"
      description="去「知识库管理」页创建知识库并上传文档后，即可开始对话。"
    />

    <div v-else class="chat-panel">
      <SessionList
        :sessions="chatStore.sessions"
        :active-id="chatStore.activeSessionId"
        :loading="chatStore.sessionsLoading"
        @select="chatStore.selectSession"
        @create="chatStore.createSession"
        @remove="removeSession"
      />

      <div class="chat-main">
        <div ref="scrollRef" class="messages">
          <div
            v-if="!chatStore.messages.length && !chatStore.streaming"
            class="welcome"
          >
            <EmptyState
              icon="💬"
              title="开始新的问答"
              description="例如：根据上传的文档，总结产品的定价规则？回答将引用知识库中的原文片段。"
            />
          </div>

          <template v-else>
            <ChatMessageItem
              v-for="(msg, i) in chatStore.messages"
              :key="(msg as { id?: number }).id ?? `live-${i}`"
              :message="msg"
            />
          </template>

          <p v-if="chatStore.error" class="error">{{ chatStore.error }}</p>
        </div>

        <ChatInput
          :streaming="chatStore.streaming"
          @send="chatStore.sendMessage"
          @stop="chatStore.stop"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-view {
  display: flex;
  flex-direction: column;
  gap: 18px;
  height: 100%;
  min-height: 0;
}

.chat-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
}

.chat-title {
  margin: 0;
  font-size: 22px;
  font-weight: 650;
}

.chat-subtitle {
  margin: 6px 0 0;
  color: var(--text-secondary);
  font-size: 13px;
}

.chat-panel {
  flex: 1;
  min-height: 0;
  display: flex;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}

.chat-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg);
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.welcome {
  margin: auto;
}

.error {
  margin: 0;
  color: var(--danger);
  background: var(--danger-weak);
  border: 1px solid rgba(229, 72, 77, 0.3);
  border-radius: var(--radius-sm);
  padding: 10px 14px;
  font-size: 13px;
}

.chat-main > :deep(.chat-input) {
  margin: 0 16px 16px;
}
</style>
