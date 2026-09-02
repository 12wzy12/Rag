<script setup lang="ts">
import { onMounted } from 'vue'

import DocumentList from '@/components/documents/DocumentList.vue'
import DocumentUpload from '@/components/documents/DocumentUpload.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import { useDocumentsStore } from '@/stores/documents'

const store = useDocumentsStore()

onMounted(() => {
  store.fetchDocuments()
})
</script>

<template>
  <div class="documents-view">
    <PageHeader
      title="知识库"
      subtitle="上传文档，系统自动切分并建立可检索索引。"
    />
    <DocumentUpload />
    <DocumentList />
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
