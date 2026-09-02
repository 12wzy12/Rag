<script setup lang="ts">
import { useDocumentsStore } from '@/stores/documents'
import { formatBytes, formatTime } from '@/utils/format'

import EmptyState from '@/components/ui/EmptyState.vue'
import Spinner from '@/components/ui/Spinner.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'

const store = useDocumentsStore()

function onRefresh() {
  store.fetchDocuments()
}

async function onDelete(id: string, name: string) {
  if (!window.confirm(`确定删除文档「${name}」吗？此操作不可撤销。`)) return
  try {
    await store.remove(id)
  } catch {
    window.alert('删除失败，请稍后重试')
  }
}
</script>

<template>
  <section class="list-card">
    <header class="list-header">
      <div class="list-title">
        <h2>文档列表</h2>
        <span v-if="store.items.length" class="count">{{ store.items.length }}</span>
      </div>
      <button class="refresh" :disabled="store.loading" @click="onRefresh">
        {{ store.loading ? '加载中…' : '刷新' }}
      </button>
    </header>

    <div v-if="store.loading && !store.items.length" class="loading">
      <Spinner />
      <span>正在加载文档…</span>
    </div>

    <EmptyState
      v-else-if="!store.items.length"
      icon="🗂️"
      title="知识库还是空的"
      description="上传你的第一批文档，系统会自动切分并建立索引。"
    />

    <table v-else class="doc-table">
      <thead>
        <tr>
          <th>文档名称</th>
          <th>大小</th>
          <th>文本块</th>
          <th>状态</th>
          <th>上传时间</th>
          <th class="col-actions"></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="doc in store.items" :key="doc.id">
          <td class="doc-name" :title="doc.name">{{ doc.name }}</td>
          <td>{{ formatBytes(doc.size) }}</td>
          <td>{{ doc.chunks }}</td>
          <td>
            <StatusBadge :status="doc.status" />
            <p v-if="doc.error" class="doc-error" :title="doc.error">{{ doc.error }}</p>
          </td>
          <td>{{ formatTime(doc.uploadedAt) }}</td>
          <td class="col-actions">
            <button class="delete" title="删除" @click="onDelete(doc.id, doc.name)">删除</button>
          </td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<style scoped>
.list-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}

.list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
}

.list-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.list-title h2 {
  margin: 0;
  font-size: 15px;
  font-weight: 650;
}

.count {
  background: var(--surface-2);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
  padding: 1px 8px;
  border-radius: 999px;
}

.refresh {
  border: 1px solid var(--border-strong);
  background: var(--surface);
  border-radius: var(--radius-sm);
  padding: 5px 12px;
  font-size: 13px;
  color: var(--text-secondary);
}

.refresh:hover:not(:disabled) {
  background: var(--surface-2);
}

.refresh:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.loading {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 40px;
  justify-content: center;
  color: var(--text-secondary);
  font-size: 13px;
}

.doc-table {
  width: 100%;
  border-collapse: collapse;
}

.doc-table th,
.doc-table td {
  text-align: left;
  padding: 12px 20px;
  font-size: 13px;
}

.doc-table th {
  color: var(--text-secondary);
  font-weight: 600;
  background: var(--surface-2);
  white-space: nowrap;
}

.doc-table tbody tr {
  border-top: 1px solid var(--surface-2);
}

.doc-table tbody tr:hover {
  background: #fafbfc;
}

.doc-name {
  font-weight: 600;
  color: var(--text);
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-error {
  margin: 2px 0 0;
  font-size: 12px;
  color: var(--danger);
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.col-actions {
  text-align: right;
}

.delete {
  border: none;
  background: none;
  color: var(--text-secondary);
  font-size: 13px;
  padding: 4px 8px;
  border-radius: var(--radius-sm);
}

.delete:hover {
  color: var(--danger);
  background: var(--danger-weak);
}
</style>
