<script setup lang="ts">
import { onMounted, watch } from 'vue'

import DocumentList from '@/components/documents/DocumentList.vue'
import DocumentUpload from '@/components/documents/DocumentUpload.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import KbSelector from '@/components/kb/KbSelector.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import { useDocumentsStore } from '@/stores/documents'
import { useKbStore } from '@/stores/kb'

const kbStore = useKbStore()
const docsStore = useDocumentsStore()

async function ensureKnowledgeBases() {
  if (!kbStore.items.length) {
    await kbStore.fetchKnowledgeBases()
  }
}

onMounted(ensureKnowledgeBases)

// 知识库切换时重新拉取文档列表。
watch(
  () => kbStore.currentKbId,
  (id) => {
    if (id != null) docsStore.fetchDocuments(id)
    else docsStore.items = []
  },
  { immediate: true },
)
</script>

<template>
  <div class="documents-view">
    <PageHeader
      title="文档上传"
      subtitle="支持 PDF / Word / Markdown / TXT 等格式，上传后自动解析、切分并向量化。"
    >
      <template #actions>
        <KbSelector v-if="kbStore.items.length" />
      </template>
    </PageHeader>

    <EmptyState
      v-if="!kbStore.items.length"
      icon="📚"
      title="请先创建知识库"
      description="文档必须归属于某个知识库，去「知识库管理」页创建一个吧。"
    />

    <template v-else>
      <DocumentUpload :kb-id="kbStore.currentKbId!" />
      <DocumentList />
    </template>
  </div>
</template>

<style scoped>
.documents-view {
  display: flex;
  flex-direction: column;
  gap: 20px;
  max-width: 960px;
}
</style>
