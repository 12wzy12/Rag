<script setup lang="ts">
import type { SearchChunk } from '@/types'

defineProps<{ source: SearchChunk }>()

function percent(value: number): string {
  return `${Math.round(value * 100)}%`
}
</script>

<template>
  <details class="source">
    <summary class="source-head">
      <span class="source-name" :title="source.document_title">
        📄 {{ source.document_title }}
      </span>
      <span v-if="source.page != null" class="page">第 {{ source.page }} 页</span>
      <span class="score">相关度 {{ percent(source.rerank_score) }}</span>
    </summary>
    <p class="source-text">{{ source.text }}</p>
  </details>
</template>

<style scoped>
.source {
  border: 1px solid var(--border);
  border-left: 3px solid var(--accent);
  border-radius: var(--radius-sm);
  background: var(--surface);
}

.source-head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  cursor: pointer;
  font-size: 12px;
  user-select: none;
  list-style: none;
}

.source-head::-webkit-details-marker {
  display: none;
}

.source-head::before {
  content: '▸';
  color: var(--muted);
  font-size: 10px;
  transition: transform 0.15s;
}

.source[open] .source-head::before {
  transform: rotate(90deg);
}

.source-name {
  font-weight: 600;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.page {
  flex-shrink: 0;
  color: var(--text-secondary);
  background: var(--surface-2);
  border-radius: var(--radius-sm);
  padding: 0 8px;
}

.score {
  margin-left: auto;
  flex-shrink: 0;
  color: var(--text-secondary);
}

.source-text {
  margin: 0;
  padding: 4px 12px 10px 24px;
  font-size: 12px;
  line-height: 1.7;
  color: var(--text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 160px;
  overflow-y: auto;
}
</style>
