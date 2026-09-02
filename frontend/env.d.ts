/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL for the RAG backend API, e.g. "http://localhost:8000". */
  readonly VITE_API_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
