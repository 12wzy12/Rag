/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** RAG 后端 API 的基础地址（Base URL），例如 "http://localhost:8000"。 */
  readonly VITE_API_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
