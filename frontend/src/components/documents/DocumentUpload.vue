<script setup lang="ts">
import { ref } from 'vue'

import { useDocumentsStore } from '@/stores/documents'
import { formatBytes } from '@/utils/format'

const store = useDocumentsStore()

const ACCEPT =
  '.pdf,.doc,.docx,.txt,.md,.xls,.xlsx,.ppt,.pptx,.csv,.html,.epub'

const inputRef = ref<HTMLInputElement | null>(null)
const pending = ref<File[]>([])
const dragging = ref(false)

function pick() {
  inputRef.value?.click()
}

function onSelect(event: Event) {
  const input = event.target as HTMLInputElement
  const files = input.files ? Array.from(input.files) : []
  if (files.length) pending.value = files
  // 重置以允许再次选择同一文件。
  input.value = ''
}

function onDrop(event: DragEvent) {
  dragging.value = false
  const files = event.dataTransfer?.files
  if (files && files.length) pending.value = Array.from(files)
}

async function startUpload() {
  if (!pending.value.length || store.uploading) return
  try {
    await store.upload(pending.value)
    pending.value = []
  } catch {
    // 错误已写入 store.uploadError，由模板展示。
  }
}
</script>

<template>
  <section class="upload">
    <div
      class="dropzone"
      :class="{ dragging }"
      role="button"
      tabindex="0"
      @click="pick"
      @keydown.enter="pick"
      @dragover.prevent="dragging = true"
      @dragleave.prevent="dragging = false"
      @drop.prevent="onDrop"
    >
      <input
        ref="inputRef"
        type="file"
        multiple
        :accept="ACCEPT"
        class="file-input"
        @change="onSelect"
      />
      <div class="dropzone-icon">⬆️</div>
      <p class="dropzone-text">
        拖拽文档到此处，或 <span class="link">点击选择文件</span>
      </p>
      <p class="dropzone-hint">支持 PDF、Word、Markdown 等常用文档格式</p>
    </div>

    <div v-if="pending.length" class="pending">
      <div class="pending-header">
        <span class="pending-count">已选择 {{ pending.length }} 个文件</span>
        <span class="pending-sum">{{ formatBytes(pending.reduce((sum, f) => sum + f.size, 0)) }}</span>
      </div>
      <ul class="pending-list">
        <li v-for="file in pending" :key="file.name + file.lastModified" class="pending-item">
          <span class="pending-name">{{ file.name }}</span>
          <span class="pending-size">{{ formatBytes(file.size) }}</span>
        </li>
      </ul>
      <div class="pending-actions">
        <button class="btn" :disabled="store.uploading" @click="pending = []">清空</button>
        <button class="btn primary" :disabled="store.uploading" @click="startUpload">
          <span v-if="store.uploading">上传中…</span>
          <span v-else>上传到知识库</span>
        </button>
      </div>
    </div>

    <div v-if="store.uploading" class="progress">
      <div class="progress-bar">
        <div class="progress-fill" :style="{ width: store.uploadProgress + '%' }" />
      </div>
      <span class="progress-label">{{ store.uploadProgress }}%</span>
    </div>

    <p v-if="store.uploadError" class="error">{{ store.uploadError }}</p>
  </section>
</template>

<style scoped>
.upload {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.dropzone {
  border: 2px dashed var(--border-strong);
  border-radius: var(--radius);
  background: var(--surface);
  padding: 36px 24px;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}

.dropzone:hover,
.dropzone.dragging {
  border-color: var(--accent);
  background: var(--accent-weak);
}

.file-input {
  display: none;
}

.dropzone-icon {
  font-size: 28px;
}

.dropzone-text {
  margin: 12px 0 0;
  font-size: 15px;
  color: var(--text);
}

.link {
  color: var(--accent);
  font-weight: 600;
}

.dropzone-hint {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--muted);
}

.pending {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 14px 16px;
}

.pending-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}

.pending-count {
  font-weight: 600;
}

.pending-sum {
  color: var(--text-secondary);
  font-size: 13px;
}

.pending-list {
  list-style: none;
  margin: 0;
  padding: 0;
  max-height: 160px;
  overflow-y: auto;
}

.pending-item {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 6px 0;
  border-bottom: 1px solid var(--surface-2);
  font-size: 13px;
  color: var(--text-secondary);
}

.pending-item:last-child {
  border-bottom: none;
}

.pending-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text);
}

.pending-size {
  flex-shrink: 0;
}

.pending-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 12px;
}

.btn {
  padding: 7px 14px;
  border: 1px solid var(--border-strong);
  background: var(--surface);
  border-radius: var(--radius-sm);
  font-size: 13px;
  color: var(--text);
  transition: background 0.15s;
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

.btn.primary:hover:not(:disabled) {
  background: var(--accent-strong);
}

.btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.progress {
  display: flex;
  align-items: center;
  gap: 12px;
}

.progress-bar {
  flex: 1;
  height: 8px;
  border-radius: 999px;
  background: var(--surface-2);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--accent);
  transition: width 0.2s;
}

.progress-label {
  font-size: 12px;
  color: var(--text-secondary);
  min-width: 36px;
  text-align: right;
}

.error {
  margin: 0;
  color: var(--danger);
  background: var(--danger-weak);
  border: 1px solid rgba(229, 72, 77, 0.3);
  border-radius: var(--radius-sm);
  padding: 10px 14px;
  font-size: 13px;
}
</style>
