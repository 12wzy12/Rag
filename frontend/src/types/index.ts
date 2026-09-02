/** Shared types for the RAG backend API. */

/** 文档在知识库中的生命周期状态。 */
export type DocStatus = 'uploading' | 'processing' | 'ready' | 'error'

export interface DocumentItem {
  /** 文档唯一标识。 */
  id: string
  /** 原文件名。 */
  name: string
  /** MIME 类型，如 application/pdf。 */
  contentType: string
  /** 原始文件字节数。 */
  size: number
  /** 已切分并索引的文本块数量。 */
  chunks: number
  /** 当前状态。 */
  status: DocStatus
  /** 上传时间（ISO 时间戳）。 */
  uploadedAt: string
  /** 处理失败时的错误信息。 */
  error?: string
}

/** 检索命中的一段文本块。 */
export interface SearchChunk {
  /** 所属文档 ID。 */
  documentId: string
  /** 所属文档名。 */
  documentName: string
  /** 文本块 ID。 */
  chunkId: string
  /** 文本块内容。 */
  text: string
  /** 相似度得分，0~1，越大越相关。 */
  score: number
  /** 来源页码（可选）。 */
  page?: number
}

export interface SearchParams {
  query: string
  /** 返回的文本块数量上限。 */
  topK?: number
}

export interface SearchResult {
  query: string
  /** 检索耗时（毫秒）。 */
  tookMs: number
  /** 实际返回的 topK。 */
  topK: number
  /** 命中的文本块列表（按相关度降序）。 */
  chunks: SearchChunk[]
}

export interface ApiError {
  message: string
  status?: number
}
