<script setup lang="ts">
import type { ChatSession } from '@/types'

defineProps<{
  sessions: ChatSession[]
  activeId: number | null
  loading: boolean
}>()

const emit = defineEmits<{
  select: [id: number]
  create: []
  remove: [id: number, title: string]
}>()

function remove(session: ChatSession) {
  emit('remove', session.id, session.title)
}
</script>

<template>
  <aside class="sessions">
    <button class="new" @click="emit('create')">＋ 新对话</button>
    <div v-if="loading" class="tip">加载中…</div>
    <div v-else-if="!sessions.length" class="tip">暂无历史会话</div>
    <ul v-else class="session-list">
      <li v-for="session in sessions" :key="session.id">
        <button
          class="session"
          :class="{ active: session.id === activeId }"
          @click="emit('select', session.id)"
        >
          <span class="session-title" :title="session.title">{{ session.title }}</span>
        </button>
        <button class="session-del" title="删除会话" @click="remove(session)">×</button>
      </li>
    </ul>
  </aside>
</template>

<style scoped>
.sessions {
  width: 240px;
  flex-shrink: 0;
  border-right: 1px solid var(--border);
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: var(--surface);
  border-radius: var(--radius) 0 0 var(--radius);
}

.new {
  padding: 9px 12px;
  border: 1px dashed var(--border-strong);
  border-radius: var(--radius-sm);
  background: var(--surface);
  color: var(--accent);
  font-size: 13px;
  font-weight: 600;
}

.new:hover {
  background: var(--accent-weak);
  border-color: var(--accent);
}

.tip {
  color: var(--muted);
  font-size: 12px;
  text-align: center;
  padding: 12px 0;
}

.session-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  overflow-y: auto;
}

.session-list li {
  display: flex;
  align-items: center;
  gap: 4px;
}

.session {
  flex: 1;
  min-width: 0;
  text-align: left;
  border: none;
  background: none;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  font-size: 13px;
}

.session:hover {
  background: var(--surface-2);
  color: var(--text);
}

.session.active {
  background: var(--accent-weak);
  color: var(--accent);
  font-weight: 600;
}

.session-title {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-del {
  flex-shrink: 0;
  border: none;
  background: none;
  color: var(--muted);
  font-size: 15px;
  line-height: 1;
  padding: 6px 8px;
  border-radius: var(--radius-sm);
  opacity: 0;
  transition: opacity 0.12s;
}

.session-list li:hover .session-del {
  opacity: 1;
}

.session-del:hover {
  color: var(--danger);
  background: var(--danger-weak);
}
</style>
