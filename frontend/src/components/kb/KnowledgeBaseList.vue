<script setup lang="ts">
import { computed } from 'vue'

import { formatTime } from '@/utils/format'

interface Props {
  kbId: number
  name: string
  description: string
  documentCount: number
  chunkCount: number
  createdAt: string
  active: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  select: []
  remove: []
}>()

const desc = computed(() => props.description.trim() || '暂无描述')
</script>

<template>
  <article class="kb-card" :class="{ active }">
    <div class="kb-main">
      <h3 class="kb-name">{{ name }}</h3>
      <p class="kb-desc" :title="description">{{ desc }}</p>
      <div class="kb-meta">
        <span class="meta-item">📄 {{ documentCount }} 文档</span>
        <span class="meta-item">🧩 {{ chunkCount }} 文本块</span>
        <span class="meta-item muted">{{ formatTime(createdAt) }}</span>
      </div>
    </div>
    <div class="kb-actions">
      <button class="btn" :class="{ primary: active }" :disabled="active" @click="emit('select')">
        {{ active ? '当前使用' : '设为当前' }}
      </button>
      <button class="btn danger" @click="emit('remove')">删除</button>
    </div>
  </article>
</template>

<style scoped>
.kb-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px 20px;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.kb-card:hover {
  border-color: var(--border-strong);
}

.kb-card.active {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-weak);
}

.kb-main {
  min-width: 0;
}

.kb-name {
  margin: 0 0 4px;
  font-size: 15px;
  font-weight: 650;
}

.kb-desc {
  margin: 0 0 8px;
  color: var(--text-secondary);
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 520px;
}

.kb-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: var(--text-secondary);
}

.kb-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.btn {
  border: 1px solid var(--border-strong);
  background: var(--surface);
  border-radius: var(--radius-sm);
  padding: 6px 14px;
  font-size: 13px;
  color: var(--text);
}

.btn:hover:not(:disabled) {
  background: var(--surface-2);
}

.btn.primary {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
  font-weight: 600;
}

.btn.primary:disabled {
  background: var(--accent-weak);
  border-color: var(--accent-weak);
  color: var(--accent);
  cursor: default;
}

.btn.danger:hover {
  color: var(--danger);
  background: var(--danger-weak);
  border-color: rgba(229, 72, 77, 0.3);
}
</style>
