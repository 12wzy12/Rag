<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'

import EmptyState from '@/components/ui/EmptyState.vue'
import KbSelector from '@/components/kb/KbSelector.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import ResultChunk from '@/components/search/ResultChunk.vue'
import SearchBar from '@/components/search/SearchBar.vue'
import Spinner from '@/components/ui/Spinner.vue'
import { useKbStore } from '@/stores/kb'
import { useSearchStore } from '@/stores/search'

const kbStore = useKbStore()
const store = useSearchStore()

const result = computed(() => store.result)

onMounted(() => {
  if (!kbStore.items.length) kbStore.fetchKnowledgeBases()
})

// 切换知识库后，历史结果不再属于当前库，清空重查。
watch(
  () => kbStore.currentKbId,
  () => store.reset(),
)

function percent(value: number | null | undefined): string {
  return value == null ? '—' : `${Math.round(value * 100)}%`
}
</script>

<template>
  <div class="search-view">
    <PageHeader
      title="语义检索"
      subtitle="向量召回 → 二阶段重排 → 相关性判定，返回带来源的高相关片段。"
    >
      <template #actions>
        <KbSelector v-if="kbStore.items.length" />
      </template>
    </PageHeader>

    <EmptyState
      v-if="!kbStore.items.length"
      icon="📚"
      title="请先创建知识库"
      description="去「知识库管理」页创建知识库并上传文档后，即可开始语义检索。"
    />

    <template v-else>
      <SearchBar />

      <div class="search-body">
        <div v-if="store.loading" class="state">
          <Spinner />
          <span>正在召回并重排检索结果…</span>
        </div>

        <p v-else-if="store.error" class="error">{{ store.error }}</p>

        <EmptyState
          v-else-if="!store.searched"
          icon="🔍"
          title="输入问题开始检索"
          description="例如：产品的定价规则是什么？"
        />

        <!-- 相关性不足被拒答：展示阈值判定，不展示弱结果 -->
        <div v-else-if="result?.refused" class="refused">
          <div class="refused-icon">🚫</div>
          <div class="refused-body">
            <h3>知识库中未找到足够相关的信息</h3>
            <p>
              最高相关度 <strong>{{ percent(result?.best_score) }}</strong>
              低于阈值 <strong>{{ percent(result?.threshold) }}</strong>，
              为避免无依据回答已拒绝给出结论。换个问法，或先向知识库补充文档。
            </p>
          </div>
        </div>

        <EmptyState
          v-else-if="!result"
          icon="😕"
          title="未找到相关结果"
          description="换个问法，或先向知识库上传更多文档。"
        />

        <template v-else>
          <div class="meta">
            命中 <strong>{{ result.results.length }}</strong> 条结果 ·
            召回 {{ result.recall_count }} 条 ·
            向量后端 {{ result.backend }} ·
            最高相关度 {{ percent(result.best_score) }}
          </div>

          <ol class="results">
            <li
              v-for="(chunk, index) in result.results"
              :key="chunk.chunk_id"
              class="result-item"
            >
              <span class="rank">{{ index + 1 }}</span>
              <ResultChunk :chunk="chunk" />
            </li>
          </ol>
        </template>
      </div>
    </template>
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

.refused {
  display: flex;
  gap: 14px;
  align-items: flex-start;
  background: var(--warning-weak);
  border: 1px solid rgba(199, 116, 0, 0.25);
  border-radius: var(--radius);
  padding: 16px 18px;
}

.refused-icon {
  font-size: 24px;
}

.refused-body h3 {
  margin: 0 0 6px;
  font-size: 14px;
  color: var(--warning);
}

.refused-body p {
  margin: 0;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.7;
}

.refused-body strong {
  color: var(--text);
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
