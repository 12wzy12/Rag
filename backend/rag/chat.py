"""SSE 聊天流：检索 -> 相关性门控 -> 流式 LLM 回答。

事件协议（每个帧为 ``event: <name>`` + ``data: <json>``）：

1. ``sources``  — 支撑回答的检索并经重排后的片段（同时携带 ``session_id``，
   新会话时会即时创建）。
2. ``chunk``    — 单个回答文本片段；可能多次到达。
3. ``done``     — 流正常结束（助手消息已持久化）。
4. ``refused``  — 相关性门控拒绝了该查询（最佳得分低于阈值），不会调用
   LLM；随后会发送 ``done``。
5. ``error``    — 检索或模型失败；流结束且不发送 ``done``。

消息（用户与助手各一条，助手轮次保留其 sources JSON）按会话持久化，
因此刷新页面后历史仍然存在，并会回放到后续追问的提示词中。
"""

import json
import logging

from django.conf import settings

from rag import llm as llm_service
from rag import services
from rag.models import Message, Session

logger = logging.getLogger(__name__)

REFUSED_ANSWER = "根据现有知识库无法回答。建议换个问法，或先向知识库补充相关文档。"


def sse(event, data):
    """格式化一个 SSE 帧。"""
    return (
        f"event: {event}\n"
        f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
    )


def _recent_history(session):
    """此前若干轮用户/助手消息，用作提示词上下文（不含当前正在回答的一轮）。"""
    messages = list(
        Message.objects.filter(session=session)
        .order_by("-id")[: 2 * int(settings.RAG_CHAT_HISTORY_TURNS)]
    )
    messages.reverse()
    return [{"role": m.role, "content": m.content} for m in messages]


def chat_stream(kb, query, session, top_k=None):
    """单轮聊天对应的 SSE 帧生成器（参见模块 docstring）。"""
    top_k = top_k or settings.RAG_DEFAULT_TOP_K
    history = _recent_history(session)
    Message.objects.create(
        session=session, role=Message.Role.USER, content=query, sources=[]
    )

    try:
        result = services.retrieve(kb, query, top_k=top_k)
    except RuntimeError as exc:
        yield sse("error", {"message": str(exc)})
        return
    except Exception as exc:  # pragma: no cover - 防御性兜底
        logger.exception("chat 检索失败")
        yield sse("error", {"message": f"检索失败: {exc}"})
        return

    sources_payload = {
        "session_id": session.id,
        "count": len(result["results"]),
        "refused": result["refused"],
        "threshold": result["threshold"],
        "best_score": result["best_score"],
        "results": result["results"],
    }
    yield sse("sources", sources_payload)

    saved = False
    collected = []
    try:
        if result["refused"]:
            message = Message.objects.create(
                session=session,
                role=Message.Role.ASSISTANT,
                content=REFUSED_ANSWER,
                sources=[],
            )
            saved = True
            yield sse(
                "refused",
                {
                    "session_id": session.id,
                    "message": REFUSED_ANSWER,
                    "threshold": result["threshold"],
                    "best_score": result["best_score"],
                },
            )
            yield sse(
                "done",
                {
                    "session_id": session.id,
                    "message_id": message.id,
                    "answer_length": len(REFUSED_ANSWER),
                },
            )
            return

        try:
            for piece in llm_service.generate_answer_stream(
                query, result["results"], history
            ):
                collected.append(piece)
                yield sse("chunk", {"text": piece})
        except RuntimeError as exc:
            yield sse("error", {"message": str(exc)})
            return

        answer = "".join(collected)
        if not answer.strip():
            yield sse("error", {"message": "模型返回了空回答"})
            return
        message = Message.objects.create(
            session=session,
            role=Message.Role.ASSISTANT,
            content=answer,
            sources=result["results"],
        )
        saved = True
        yield sse(
            "done",
            {
                "session_id": session.id,
                "message_id": message.id,
                "answer_length": len(answer),
            },
        )
    finally:
        # 客户端断开（GeneratorExit / BrokenPipe）：把已流出的内容
        # 持久化，保证对话历史保持一致。
        if not saved and collected:
            partial = "".join(collected).strip()
            if partial:
                try:
                    Message.objects.create(
                        session=session,
                        role=Message.Role.ASSISTANT,
                        content=partial,
                        sources=result.get("results", []),
                    )
                except Exception:
                    logger.exception("保存不完整回答失败")
