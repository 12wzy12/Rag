<script setup lang="ts">
import { onMounted } from 'vue'

import EmptyState from '@/components/ui/EmptyState.vue'
import KnowledgeBaseForm from '@/components/kb/KnowledgeBaseForm.vue'
import KnowledgeBaseList from '@/components/kb/KnowledgeBaseList.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import Spinner from '@/components/ui/Spinner.vue'
import { useKbStore } from '@/stores/kb'

const store = useKbStore()

onMounted(() => {
  if (!store.items.length) store.fetchKnowledgeBases()
})

async function removeKb(id: number, name: string) {
  if (!window.confirm(`确定删除知识库「${name}」吗？其中的文档与向量数据将一并删除。`)) return
  try {
    await store.remove(id)
  } catch {
    window.alert('删除失败，请稍后重试')
  }
}
</script>

<template>
  <div class="kb-view">
    <PageHeader
      title="知识库管理"
      subtitle="每个知识库拥有独立的文档集与向量索引，可创建多个库分别管理不同主题的文档。"
    />
    <KnowledgeBaseForm />

    <div v-if="store.loading && !store.items.length" class="state">
      <Spinner />
      <span>正在加载知识库…</span>
    </div>

    <p v-else-if="store.error" class="error">{{ store.error }}</p>

    <EmptyState
      v-else-if="!store.items.length"
      icon="📚"
      title="还没有知识库"
      description="点击上方「新建知识库」，然后前往「文档上传」页面上传文档。"
    />

    <div v-else class="list">
      <KnowledgeBaseList
        v-for="kb in store.items"
        :key="kb.id"
        :kb-id="kb.id"
        :name="kb.name"
        :description="kb.description"
        :document-count="kb.document_count"
        :chunk-count="kb.chunk_count"
        :created-at="kb.created_at"
        :active="kb.id === store.currentKbId"
        @select="store.select(kb.id)"
        @remove="removeKb(kb.id, kb.name)"
      />
    </div>
  </div>
</template>

<style scoped>
.kb-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 960px;
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

.list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
</style>
