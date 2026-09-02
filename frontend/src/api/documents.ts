import { http } from './client'

import type { DocumentItem } from '@/types'

/** 拉取知识库中的全部文档。 */
export async function listDocuments(): Promise<DocumentItem[]> {
  const { data } = await http.get<DocumentItem[]>('/documents')
  return data
}

/**
 * 上传一个或多个文档文件。
 * @param files 待上传文件。
 * @param onProgress 上传进度回调（0~100）。
 */
export async function uploadDocuments(
  files: File[],
  onProgress?: (percent: number) => void,
): Promise<DocumentItem[]> {
  const form = new FormData()
  for (const file of files) form.append('files', file)

  const { data } = await http.post<DocumentItem[]>('/documents/upload', form, {
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

/** 删除指定文档。 */
export async function deleteDocument(id: string): Promise<void> {
  await http.delete(`/documents/${id}`)
}
