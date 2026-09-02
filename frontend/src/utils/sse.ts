/**
 * 手写 SSE 帧解析（用于 POST 流式接口）。
 *
 * 为什么不直接用 EventSource：EventSource 只支持 GET；聊天接口是
 * POST /chat/。为什么不用 axios：浏览器端 axios 基于 XHR，拿不到
 * 流式响应体，必须用原生 fetch + ReadableStream。
 *
 * 注意：用 `new TextDecoder('utf-8', { stream: true })` 处理增量解码，
 * 否则中文等多字节字符在跨 chunk 边界时会被解码成乱码。
 */

export type SseHandler = (event: string, data: unknown) => void

function parseFrame(frame: string, onEvent: SseHandler): void {
  let event = 'message'
  const dataLines: string[] = []
  for (const line of frame.split('\n')) {
    if (line.startsWith('event:')) {
      event = line.slice(6).trim()
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).replace(/^ /, ''))
    }
  }
  if (!dataLines.length) return
  const raw = dataLines.join('\n')
  let parsed: unknown = raw
  try {
    parsed = JSON.parse(raw)
  } catch {
    // 非 JSON data 保持原文透传。
  }
  onEvent(event, parsed)
}

/**
 * 消费一个已发出的 fetch Response，逐帧回调。
 * @param signal 传入 AbortController 信号；中断时取消底层读取。
 */
export async function consumeSse(
  response: Response,
  onEvent: SseHandler,
  signal?: AbortSignal,
): Promise<void> {
  if (!response.ok) {
    let detail = `请求失败（HTTP ${response.status}）`
    try {
      const payload = (await response.json()) as { detail?: string }
      if (payload.detail) detail = payload.detail
    } catch {
      // 非 JSON 错误体，使用默认文案。
    }
    throw new Error(detail)
  }
  if (!response.body) throw new Error('响应不支持流式读取')

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  const onAbort = () => {
    reader.cancel().catch(() => undefined)
  }
  signal?.addEventListener('abort', onAbort, { once: true })

  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      let sep: number
      while ((sep = buffer.indexOf('\n\n')) !== -1) {
        const frame = buffer.slice(0, sep)
        buffer = buffer.slice(sep + 2)
        if (frame.trim()) parseFrame(frame, onEvent)
      }
    }
    buffer += decoder.decode()
    if (buffer.trim()) parseFrame(buffer, onEvent)
  } finally {
    signal?.removeEventListener('abort', onAbort)
  }
}
