/** 与后端 REST / SSE 契约一一对应的类型定义。 */

/** 文档生命周期状态（与后端 Document.Status 一致）。 */
export type DocStatus = 'pending' | 'parsing' | 'ready' | 'failed'

export interface KnowledgeBase {
  id: number
  name: string
  description: string
  document_count: number
  chunk_count: number
  created_at: string
}

export interface DocumentItem {
  id: number
  /** 所属知识库 id。 */
  kb: number
  /** 所属知识库名称。 */
  knowledge_base: string
  title: string
  file_name: string
  content_type: string
  size: number
  status: DocStatus
  error: string
  chunk_count: number
  created_at: string
  updated_at: string
}

export interface DocumentUploadResult {
  message: string
  chunk_count: number
  document: DocumentItem
}

/** 检索命中的一段文本块（含向量分与重排分）。 */
export interface SearchChunk {
  score: number
  rerank_score: number
  chunk_id: number
  document_id: number
  document_title: string
  chunk_index: number
  /** 来源页码（PDF），纯文本/Word 为 null。 */
  page: number | null
  text: string
}

/** /search 的统一返回信封。 */
export interface SearchResult {
  query: string
  kb_id: number
  knowledge_base: string
  count: number
  /** 相关性不足被拒答：results 恒为空。 */
  refused: boolean
  threshold: number
  best_score: number
  /** 实际使用的向量后端（milvus / memory）。 */
  backend: string
  recall_count: number
  results: SearchChunk[]
}

export interface ChatSession {
  id: number
  kb: number
  title: string
  created_at: string
}

export interface ChatMessage {
  id: number
  session: number
  role: 'user' | 'assistant'
  content: string
  /** assistant 回答的知识来源（重排后片段）。 */
  sources: SearchChunk[]
  created_at: string
}

/** SSE 聊天事件载荷（与后端 chat.py 对齐）。 */
export interface ChatSourcesEvent {
  session_id: number
  count: number
  refused: boolean
  threshold: number
  best_score: number
  results: SearchChunk[]
}

export interface ChatDoneEvent {
  session_id: number
  message_id: number
  answer_length: number
}

export interface ChatRefusedEvent {
  session_id: number
  message: string
  threshold: number
  best_score: number
}
