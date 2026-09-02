import axios from 'axios'

/**
 * 全局 HTTP 客户端。
 *
 * baseURL 优先取环境变量 VITE_API_URL；未设置时使用相对路径 `/api`，
 * 由 vite.config.ts 中的开发代理转发到真实后端，避免开发期跨域问题。
 */
const baseURL = import.meta.env.VITE_API_URL ?? '/api'

export const http = axios.create({
  baseURL,
  timeout: 30000,
})

/** 从任意错误中提取可展示的消息，供 UI 层直接使用。 */
export function getErrorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const data = err.response?.data
    if (data && typeof data === 'object') {
      for (const key of ['message', 'detail']) {
        if (key in data && typeof data[key] === 'string') return data[key]
      }
    }
    if (err.message) return err.message
  }
  if (err instanceof Error) return err.message
  return '请求失败'
}
