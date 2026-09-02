<script setup lang="ts">
import SourceCard from '@/components/chat/SourceCard.vue'
import type { SearchChunk } from '@/types'

/** 渲染用消息：兼容 store 里“流式中”的临时消息与后端持久化消息。 */
interface ViewChatMessage {
  id?: number
  role: 'user' | 'assistant'
  content: string
  sources?: SearchChunk[]
  streaming?: boolean
  refused?: boolean
  error?: string
}

defineProps<{ message: ViewChatMessage }>()
</script>

<template>
  <div class="msg" :class="message.role">
    <div class="avatar">{{ message.role === 'user' ? '👤' : '🤖' }}</div>
    <div class="bubble-wrap">
      <div class="bubble">
        <span v-if="message.role === 'assistant' && message.streaming" class="typing-dot" />
        <span v-if="message.refused" class="refused-tag">无足够依据，已拒绝</span>
        <p class="content">{{ message.content }}<span v-if="message.streaming && !message.content" class="caret">…</span></p>
        <p v-if="message.error && !message.streaming" class="error">{{ message.error }}</p>
      </div>
      <div v-if="message.role === 'assistant' && message.sources?.length" class="sources">
        <div class="sources-title">来源引用（{{ message.sources.length }}）</div>
        <SourceCard v-for="(source, i) in message.sources" :key="source.chunk_id + '-' + i" :source="source" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.msg {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.msg.user {
  flex-direction: row-reverse;
}

.avatar {
  flex-shrink: 0;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: var(--surface-2);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
}

.msg.user .avatar {
  background: var(--accent-weak);
}

.bubble-wrap {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 78%;
  min-width: 0;
}

.msg.user .bubble-wrap {
  align-items: flex-end;
}

.bubble {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 12px 16px;
  position: relative;
}

.msg.user .bubble {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}

.typing-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  margin-right: 8px;
  border-radius: 50%;
  background: var(--accent);
  vertical-align: middle;
  animation: pulse 1.1s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 0.25; transform: scale(0.8); }
  50% { opacity: 1; transform: scale(1); }
}

.refused-tag {
  display: inline-block;
  margin-bottom: 6px;
  background: var(--warning-weak);
  color: var(--warning);
  font-size: 11px;
  font-weight: 600;
  border-radius: var(--radius-sm);
  padding: 2px 8px;
}

.content {
  margin: 0;
  font-size: 14px;
  line-height: 1.75;
  white-space: pre-wrap;
  word-break: break-word;
}

.caret {
  color: var(--accent);
  animation: blink 1s infinite;
}

.msg.user .caret {
  color: #fff;
}

@keyframes blink {
  50% { opacity: 0; }
}

.error {
  margin: 6px 0 0;
  color: var(--danger);
  font-size: 12px;
}

.sources {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
}

.sources-title {
  font-size: 11px;
  color: var(--muted);
  margin-bottom: 2px;
}
</style>
