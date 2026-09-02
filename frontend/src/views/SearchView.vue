<script setup lang="ts">
import { computed } from 'vue'

import ResultChunk from '@/components/search/ResultChunk.vue'
import SearchBar from '@/components/search/SearchBar.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import Spinner from '@/components/ui/Spinner.vue'
import { useSearchStore } from '@/stores/search'

const store = useSearchStore()

const result = computed(() => store.result)
</script>

<template>
  <div class="search-view">
    <PageHeader title="检索" subtitle="基于语义检索知识库，获取最相关的文本片段。" />
    <SearchBar />

    <div class="search-body">
      <div v-if="store.loading" class="state">
        <Spinner />
        <span>正在检索知识库…</span>
      </div>

      <p v-else-if="store.error" class="error">{{ store.error }}</p>

      <EmptyState
        v-else-if="!store.searched"
        icon="🔍"
        title="输入问题开始检索"
        description="例如：产品的定价规则是什么？"
      />

      <EmptyState
        v-else-if="!result"
        icon="😕"
        title="未找到相关结果"
        description="换个问法，或先向知识库上传更多文档。"
      />

      <template v-else>
        <div class="meta">
          命中 <strong>{{ result.chunks.length }}</strong> 条结果 · 耗时
          <strong>{{ result.tookMs }}ms</strong>
        </div>

        <ol class="results">
          <li v-for="(chunk, index) in result.chunks" :key="chunk.chunkId" class="result-item">
            <span class="rank">{{ index + 1 }}</span>
            <ResultChunk :chunk="chunk" />
          </li>
        </ol>
      </template>
    </div>
  </div>
</template>

<style scoped>
.search-view {
  max-width: 960px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.search-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.state {
  display: flex;
  align-items: center;
  gap: 10px;
  justify-content: center;
  padding: 48px 0;
  color: var(--text-secondary);
  font-size: 13px;
}

.error {
  margin: 0;
  color: var(--danger);
  background: var(--danger-weak);
  border: 1px solid rgba(229, 72, 77, 0.3);
  border-radius: var(--radius-sm);
  padding: 12px 16px;
  font-size: 13px;
}

.meta {
  font-size: 13px;
  color: var(--text-secondary);
}

.meta strong {
  color: var(--text);
}

.results {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.result-item {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.rank {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--accent-weak);
  color: var(--accent);
  font-size: 12px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 14px;
}
</style>
