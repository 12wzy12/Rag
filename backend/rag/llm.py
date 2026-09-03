"""基于检索片段生成回答。

支持两种模型服务提供方：

- ``ollama``（默认）：通过本机运行的 Ollama 服务在本地生成
  （如 ``qwen3:8b``），无需网络或 API 密钥。
- ``openai``：OpenAI 兼容的 ``/chat/completions`` 接口
  （如 DeepSeek），通过 settings 进行配置。

两个提供方都支持流式输出（``generate_answer_stream``），SSE 聊天接口
即基于此实现；``generate_answer`` 是非流式版本，供旧的 ``/answer``
接口使用。

检索接口（``/search``）不依赖本模块；这些辅助函数只服务于可选的
``/answer`` 与 ``/chat`` 接口。
"""

import json
import urllib.error
import urllib.request

from django.conf import settings


def is_configured():
    """判断配置的 LLM 提供方当前是否可用。"""
    if settings.RAG_LLM_PROVIDER == "openai":
        return bool(settings.RAG_LLM_BASE_URL and settings.RAG_LLM_API_KEY)
    # ollama 提供方视为始终可用；实际失败会在调用时暴露。
    return True


def _format_chunks(chunks):
    return "\n\n".join(
        f"[片段 {i + 1}]{'（第' + str(c['page']) + '页）' if c.get('page') else ''}\n{c['text']}"
        for i, c in enumerate(chunks)
    )


def _build_prompt(query, chunks):
    """仅包含检索上下文（无对话历史）的单条用户消息。"""
    return (
        "你是知识库问答助手。请仅依据以下检索到的文档片段回答用户问题。"
        "若片段无法回答问题，请明确说明'根据现有知识库无法回答'。"
        "回答使用中文，结合片段内容，不要编造信息。\n\n"
        f"检索到的文档片段：\n{_format_chunks(chunks)}\n\n"
        f"用户问题：{query}\n\n"
        "回答："
    )


def _build_chat_messages(query, chunks, history=None):
    """聊天接口的消息列表：系统指令 + 最近对话历史（如有）
    + 携带检索上下文的当前问题。

    ``history``：来自对话前几轮的 ``{"role": "user"|"assistant", "content": str}``
    消息列表。
    """
    context = _format_chunks(chunks)
    turns = settings.RAG_CHAT_HISTORY_TURNS
    history = history or []
    recent = history[-2 * int(turns):]

    if not recent:
        return [{"role": "user", "content": _build_prompt(query, chunks)}]

    system = (
        "你是知识库问答助手。请仅依据检索到的文档片段与对话历史回答用户问题。"
        "若片段无法回答问题，请明确说明'根据现有知识库无法回答'。"
        "回答使用中文，结合片段内容，不要编造信息，保持上下文一致。"
    )
    messages = [{"role": "system", "content": system}]
    messages.extend(recent)
    messages.append(
        {
            "role": "user",
            "content": (
                "检索到的文档片段：\n"
                f"{context}\n\n"
                f"用户问题：{query}\n\n"
                "回答："
            ),
        }
    )
    return messages


def _timeout():
    return getattr(settings, "RAG_LLM_TIMEOUT", 300)


def _stream_ollama(query, chunks, history):
    import ollama

    client = ollama.Client(host=settings.RAG_OLLAMA_BASE_URL, timeout=_timeout())
    messages = _build_chat_messages(query, chunks, history)
    stream = client.chat(
        model=settings.RAG_LLM_MODEL,
        messages=messages,
        options={"temperature": 0.2},
        keep_alive=settings.RAG_OLLAMA_KEEP_ALIVE,
        stream=True,
    )
    for piece in stream:
        content = piece.get("message", {}).get("content", "")
        if content:
            yield content


def _stream_openai(query, chunks, history):
    payload = {
        "model": settings.RAG_LLM_MODEL,
        "messages": _build_chat_messages(query, chunks, history),
        "temperature": 0.2,
        "stream": True,
    }
    req = urllib.request.Request(
        f"{settings.RAG_LLM_BASE_URL.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.RAG_LLM_API_KEY}",
        },
        method="POST",
    )
    proxy = settings.RAG_LLM_HTTP_PROXY
    if proxy:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy})
        )
    else:
        opener = urllib.request.build_opener()

    try:
        resp = opener.open(req, timeout=_timeout())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"模型接口返回 {exc.code}: {body[:300]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"无法连接模型服务: {exc.reason}") from exc

    with resp:
        for raw in resp:
            line = raw.decode("utf-8", errors="replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if not data or data == "[DONE]":
                break
            try:
                delta = json.loads(data)["choices"][0]["delta"].get("content")
            except (KeyError, IndexError, TypeError, json.JSONDecodeError):
                continue
            if delta:
                yield delta


def generate_answer_stream(query, chunks, history=None):
    """以 ``chunks`` 为依据为 ``query`` 流式生成回答片段。

    随生成进度逐段产出回答文本。模型调用失败或模型完全未产出内容时，
    抛出携带可读信息的 ``RuntimeError``。
    """
    if not query or not chunks:
        raise RuntimeError("缺少查询或检索上下文")

    try:
        if settings.RAG_LLM_PROVIDER == "openai":
            pieces = _stream_openai(query, chunks, history)
        else:
            pieces = _stream_ollama(query, chunks, history)
        total = []
        for piece in pieces:
            total.append(piece)
            yield piece
    except RuntimeError:
        raise
    except Exception as exc:  # 客户端库的网络传输/解析等临时性错误
        raise RuntimeError(f"模型调用失败: {exc}") from exc

    if not "".join(total).strip():
        raise RuntimeError("模型返回了空回答")


def generate_answer(query, chunks, history=None, timeout=300):
    """非流式回答：拼接 :func:`generate_answer_stream` 的输出。

    返回 ``(answer_text, sources_count)``；模型调用失败时抛出携带
    可读信息的 ``RuntimeError``。
    """
    pieces = list(generate_answer_stream(query, chunks, history))
    return "".join(pieces), len(chunks)
