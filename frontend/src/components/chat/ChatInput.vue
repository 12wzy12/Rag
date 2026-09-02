<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{ streaming: boolean }>()
const emit = defineEmits<{
  send: [text: string]
  stop: []
}>()

const draft = ref('')

function submit() {
  const text = draft.value.trim()
  if (!text || props.streaming) return
  draft.value = ''
  emit('send', text)
}

function onKeydown(event: KeyboardEvent) {
  // Enter 发送；Shift+Enter 换行。
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    submit()
  }
}
</script>

<template>
  <div class="chat-input">
    <textarea
      v-model="draft"
      rows="2"
      class="field"
      placeholder="输入问题，Enter 发送，Shift+Enter 换行。回答将基于知识库检索内容并标注来源。"
      @keydown="onKeydown"
    />
    <button v-if="streaming" class="btn stop" @click="emit('stop')">⏹ 停止生成</button>
    <button v-else class="btn primary" :disabled="!draft.trim()" @click="submit">发送</button>
  </div>
</template>

<style scoped>
.chat-input {
  display: flex;
  gap: 10px;
  align-items: flex-end;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 12px;
}

.field {
  flex: 1;
  resize: none;
  border: none;
  outline: none;
  background: transparent;
  font-size: 14px;
  font-family: var(--font);
  color: var(--text);
  line-height: 1.6;
  max-height: 160px;
}

.field::placeholder {
  color: var(--muted);
}

.btn {
  flex-shrink: 0;
  padding: 10px 20px;
  border: none;
  border-radius: var(--radius);
  font-size: 14px;
  font-weight: 600;
  color: #fff;
  background: var(--accent);
  white-space: nowrap;
}

.btn:hover:not(:disabled) {
  background: var(--accent-strong);
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn.stop {
  background: var(--danger);
}

.btn.stop:hover {
  background: #cf3b40;
}
</style>
