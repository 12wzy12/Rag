import { defineStore } from 'pinia'
import { ref } from 'vue'

import * as api from '@/api/documents'
import { getErrorMessage } from '@/api/client'

import type { DocumentItem } from '@/types'

export const useDocumentsStore = defineStore('documents', () => {
  const items = ref<DocumentItem[]>([])
  const loading = ref(false)
  const uploadError = ref<string | null>(null)
  const uploadProgress = ref(0)
  const uploading = ref(false)

  async function fetchDocuments() {
    loading.value = true
    try {
      items.value = await api.listDocuments()
    } finally {
      loading.value = false
    }
  }

  async function upload(files: File[]) {
    if (files.length === 0) return
    uploadError.value = null
    uploadProgress.value = 0
    uploading.value = true
    try {
      const created = await api.uploadDocuments(files, (pct) => {
        uploadProgress.value = pct
      })
      items.value = [...created, ...items.value]
    } catch (err) {
      uploadError.value = getErrorMessage(err)
      throw err
    } finally {
      uploading.value = false
    }
  }

  async function remove(id: string) {
    await api.deleteDocument(id)
    items.value = items.value.filter((doc) => doc.id !== id)
  }

  return {
    items,
    loading,
    uploadError,
    uploadProgress,
    uploading,
    fetchDocuments,
    upload,
    remove,
  }
})
