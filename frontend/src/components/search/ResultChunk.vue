<script setup lang="ts">
import { computed, ref } from 'vue'

import type { SearchChunk } from '@/types'

const props = defineProps<{ chunk: SearchChunk }>()

const copied = ref(false)

const scoreText = computed(() => `${Math.round(props.chunk.score * 100)}%`)

const scoreClass = computed(() => {
  if (props.chunk.score >= 0.6) return 'high'
  if (props.chunk.score >= 0.3) return 'mid'
  return 'low'
})

async function copy() {
  try {
    await navigator.clipboard.writeText(props.chunk.text)
    copied.value = true
    setTimeout(() => (copied.value = false), 1500)
  } catch {
    // 剪贴板权限不可用时静默忽略。
  }
}
</script>

<template>
  <article class="chunk">
    <div class="chunk-head">
      <div class="source">
        <span class="doc-name" :title="chunk.documentName">{{ chunk.documentName }}</span>
        <span v-if="chunk.page != null" class="page">第 {{ chunk.page }} 页</span>
      </div>
      <div class="chunk-meta">
        <span class="score" :class="scoreClass" :title="`相似度 ${scoreText}`">{{ scoreText }}</span>
        <button class="copy" :class="{ copied }" @click="copy">
          {{ copied ? '已复制' : '复制' }}
        </button>
      </div>
    </div>
    <p class="chunk-text">{{ chunk.text }}</p>
  </article>
</template>

<style scoped>
.chunk {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 14px 16px;
  transition: border-color 0.15s;
}

.chunk:hover {
  border-color: var(--border-strong);
}

.chunk-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.source {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.doc-name {
  font-weight: 650;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.page {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--text-secondary);
  background: var(--surface-2);
  border-radius: var(--radius-sm);
  padding: 1px 8px;
}

.chunk-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.score {
  font-size: 13px;
  font-weight: 700;
}

.score.high {
  color: var(--success);
}

.score.mid {
  color: var(--warning);
}

.score.low {
  color: var(--muted);
}

.copy {
  border: 1px solid var(--border-strong);
  background: var(--surface);
  border-radius: var(--radius-sm);
  padding: 3px 10px;
  font-size: 12px;
  color: var(--text-secondary);
}

.copy:hover {
  background: var(--surface-2);
}

.copy.copied {
  color: var(--success);
  border-color: var(--success);
  background: var(--success-weak);
}

.chunk-text {
  margin: 0;
  font-size: 13px;
  line-height: 1.75;
  color: var(--text);
  white-space: pre-wrap;
  word-break: break-word;
  font-family: var(--font);
}
</style>
