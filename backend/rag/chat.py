"""SSE chat stream: retrieval -> relevance gate -> streamed LLM answer.

Event protocol (each frame is ``event: <name>`` + ``data: <json>``):

1. ``sources``  — retrieved, reranked chunks backing the answer (also carries
   the ``session_id``, which is created on the fly for new conversations).
2. ``chunk``    — one answer text fragment; may arrive many times.
3. ``done``     — normal end of stream (assistant message persisted).
4. ``refused``  — the relevance gate rejected the query (best score below
   threshold); the LLM is never called. Followed by ``done``.
5. ``error``    — retrieval or model failure; stream ends without ``done``.

Messages (user + assistant, assistant turns keep their sources JSON) are
persisted per session so history survives page reloads and is replayed into
the prompt for follow-up questions.
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
    """Format one SSE frame."""
    return (
        f"event: {event}\n"
        f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
    )


def _recent_history(session):
    """Previous user/assistant turns for prompt context (excludes the turn
    currently being answered)."""
    messages = list(
        Message.objects.filter(session=session)
        .order_by("-id")[: 2 * int(settings.RAG_CHAT_HISTORY_TURNS)]
    )
    messages.reverse()
    return [{"role": m.role, "content": m.content} for m in messages]


def chat_stream(kb, query, session, top_k=None):
    """Generator of SSE frames for one chat turn (see module docstring)."""
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
    except Exception as exc:  # pragma: no cover - defensive
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
        # Client disconnect (GeneratorExit / BrokenPipe): persist whatever
        # streamed so far so the conversation history stays consistent.
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
