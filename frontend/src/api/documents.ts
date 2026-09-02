import { http } from './client'

import type { DocumentItem, DocumentUploadResult } from '@/types'

/** 拉取某知识库下的全部文档。 */
export async function listDocuments(kbId: number): Promise<DocumentItem[]> {
  const { data } = await http.get<DocumentItem[]>('/documents', {
    params: { kb: kbId },
  })
  return data
}

/**
 * 上传单个文档（后端同步完成解析与向量化，可能较慢，因此不设超时）。
 * @param onProgress 上传进度回调（0~100，仅网络传输阶段）。
 */
export async function uploadDocument(
  kbId: number,
  file: File,
  onProgress?: (percent: number) => void,
): Promise<DocumentUploadResult> {
  const form = new FormData()
  form.append('file', file)
  form.append('kb', String(kbId))

  const { data } = await http.post<DocumentUploadResult>('/documents', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 0,
    onUploadProgress: (event) => {
      if (event.total) {
        onProgress?.(Math.round((event.loaded / event.total) * 100))
      }
    },
  })
  return data
}

/** 删除指定文档（后端同步清除其向量）。 */
export async function deleteDocument(id: number): Promise<void> {
  await http.delete(`/documents/${id}`)
}
