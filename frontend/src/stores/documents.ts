import { defineStore } from 'pinia'
import { ref } from 'vue'

import * as api from '@/api/documents'
import { getErrorMessage } from '@/api/client'

import type { DocumentItem } from '@/types'

export const useDocumentsStore = defineStore('documents', () => {
  const items = ref<DocumentItem[]>([])
  const kbId = ref<number | null>(null)
  const loading = ref(false)
  const uploadError = ref<string | null>(null)
  const uploading = ref(false)
  /** 已上传文件数 / 总数（多文件循环上传用）。 */
  const uploadProgress = ref(0)
  const uploadTotal = ref(0)
  const uploadDone = ref(0)

  async function fetchDocuments(targetKbId: number) {
    kbId.value = targetKbId
    loading.value = true
    try {
      items.value = await api.listDocuments(targetKbId)
    } catch (err) {
      uploadError.value = getErrorMessage(err)
    } finally {
      loading.value = false
    }
  }

  /** 多文件逐个串行上传；每完成一个刷新本地列表。 */
  async function upload(targetKbId: number, files: File[]) {
    if (!files.length || uploading.value) return
    uploadError.value = null
    uploading.value = true
    uploadDone.value = 0
    uploadTotal.value = files.length
    uploadProgress.value = 0
    try {
      for (let i = 0; i < files.length; i += 1) {
        const file = files[i]
        await api.uploadDocument(targetKbId, file, (pct) => {
          uploadProgress.value = Math.round(
            ((i + pct / 100) / files.length) * 100,
          )
        })
        uploadDone.value = i + 1
        uploadProgress.value = Math.round((uploadDone.value / files.length) * 100)
      }
      await fetchDocuments(targetKbId)
    } catch (err) {
      uploadError.value = getErrorMessage(err)
      throw err
    } finally {
      uploading.value = false
    }
  }

  async function remove(id: number) {
    await api.deleteDocument(id)
    items.value = items.value.filter((doc) => doc.id !== id)
  }

  return {
    items,
    kbId,
    loading,
    uploadError,
    uploadProgress,
    uploadTotal,
    uploadDone,
    uploading,
    fetchDocuments,
    upload,
    remove,
  }
})
