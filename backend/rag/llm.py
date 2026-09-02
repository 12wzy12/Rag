"""Answer generation on top of retrieved chunks.

Two providers are supported:

- ``ollama`` (default): generate locally via a running Ollama server
  (e.g. ``qwen3:8b``). No network or API key required.
- ``openai``: an OpenAI-compatible ``/chat/completions`` endpoint
  (e.g. DeepSeek) configured through settings.

The retrieval endpoint (``/search``) does not depend on this module; these
helpers only power the optional ``/answer`` endpoint.
"""

import json
import urllib.error
import urllib.request

from django.conf import settings


def is_configured():
    """Whether the configured LLM provider is available."""
    if settings.RAG_LLM_PROVIDER == "openai":
        return bool(settings.RAG_LLM_BASE_URL and settings.RAG_LLM_API_KEY)
    # ollama provider is considered available; failures surface at call time.
    return True


def _build_prompt(query, chunks):
    context = "\n\n".join(
        f"[片段 {i + 1}]\n{chunk['text']}" for i, chunk in enumerate(chunks)
    )
    return (
        "你是知识库问答助手。请仅依据以下检索到的文档片段回答用户问题。"
        "若片段无法回答问题，请明确说明'根据现有知识库无法回答'。"
        "回答使用中文，结合片段内容，不要编造信息。\n\n"
        f"检索到的文档片段：\n{context}\n\n"
        f"用户问题：{query}\n\n"
        "回答："
    )


def _generate_ollama(query, chunks, timeout):
    import ollama

    client = ollama.Client(host=settings.RAG_OLLAMA_BASE_URL, timeout=timeout)
    response = client.chat(
        model=settings.RAG_LLM_MODEL,
        messages=[{"role": "user", "content": _build_prompt(query, chunks)}],
        options={"temperature": 0.2},
        keep_alive=settings.RAG_OLLAMA_KEEP_ALIVE,
    )
    answer = response["message"]["content"].strip()
    if not answer:
        raise RuntimeError("模型返回了空回答")
    return answer


def _generate_openai(query, chunks, timeout):
    payload = {
        "model": settings.RAG_LLM_MODEL,
        "messages": [{"role": "user", "content": _build_prompt(query, chunks)}],
        "temperature": 0.2,
        "stream": False,
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
        with opener.open(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"模型接口返回 {exc.code}: {body[:300]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"无法连接模型服务: {exc.reason}") from exc

    try:
        return data["choices"][0]["message"]["content"].strip(), len(chunks)
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"模型返回格式异常: {str(data)[:300]}") from exc


def generate_answer(query, chunks, timeout=300):
    """Ask the configured LLM to answer ``query`` from ``chunks``.

    Returns ``(answer_text, sources_count)``. Raises ``RuntimeError`` with a
    readable message on model-call failure.
    """
    if not query or not chunks:
        raise RuntimeError("缺少查询或检索上下文")

    if settings.RAG_LLM_PROVIDER == "openai":
        answer, n = _generate_openai(query, chunks, timeout)
    else:
        answer = _generate_ollama(query, chunks, timeout)
    return answer, len(chunks)
