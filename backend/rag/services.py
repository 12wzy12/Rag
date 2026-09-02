"""RAG ingestion and retrieval services.

Ingestion pipeline (per uploaded document):

    file bytes -> :func:`parsers.extract_text` (per page, with page numbers
    for PDFs) -> :func:`chunking.chunk_pages` (LlamaIndex SentenceSplitter)
    -> ``Chunk`` rows in MySQL (business data) -> embedding batch (BGE-M3 via
    Ollama by default) -> vectors upserted into Milvus (vector data).

Retrieval pipeline (multi-stage, per query):

    embed query -> first stage: Milvus vector recall (top_k * recall
    multiplier, capped) -> second stage: :func:`reranker.rerank` hybrid
    rerank -> decorate with document metadata -> relevance gate: when no
    chunk clears ``RAG_SIMILARITY_THRESHOLD`` the query is *refused*
    (``refused=True``, empty results) so the caller never hands a weak
    context to the LLM.
"""

import logging

from django.conf import settings

from rag import chunking, parsers, rag_engine, reranker, vector_store
from rag.models import Chunk, Document

logger = logging.getLogger(__name__)


def _embed_texts(texts):
    """Embed a list of texts with the configured embedding model (BGE-M3 via
    Ollama by default). Raises ``RuntimeError`` on service failure."""
    embed_model = rag_engine.get_embed_model()
    batch_size = settings.RAG_EMBED_BATCH_SIZE
    embeddings = []
    try:
        for start in range(0, len(texts), batch_size):
            embeddings.extend(
                embed_model.get_text_embedding_batch(
                    texts[start : start + batch_size]
                )
            )
    except Exception as exc:
        raise RuntimeError(
            "无法连接 Embedding 服务（Ollama bge-m3），请确认已运行并拉取模型"
        ) from exc
    return embeddings


def _embed_query(query):
    embed_model = rag_engine.get_embed_model()
    try:
        return embed_model.get_query_embedding(query)
    except Exception as exc:
        raise RuntimeError(
            "无法连接 Embedding 服务（Ollama bge-m3），请确认已运行并拉取模型"
        ) from exc


def ingest_document(document, raw_bytes, content_type, file_name):
    """Parse, chunk and vector-index a :class:`Document`.

    Replaces any previously indexed chunks for the same document. On
    success the document is marked ``ready``; failures mark it ``failed``
    with a readable error (unsupported formats raise ``ValueError``,
    everything else a ``RuntimeError`` for the caller to surface as 503).
    """
    document.status = Document.Status.PARSING
    document.error = ""
    document.save(update_fields=["status", "error", "updated_at"])

    try:
        pages = parsers.extract_text(raw_bytes, content_type, file_name)
    except ValueError as exc:
        _mark_failed(document, str(exc))
        raise

    chunks_payload = chunking.chunk_pages(pages)

    backend = vector_store.get_backend()

    # Vector backend is Milvus: embeddings must be produced before any
    # chunk row is written, so an embedding outage leaves no half-state.
    embeddings = None
    if backend.name == "milvus":
        embeddings = _embed_texts([c["text"] for c in chunks_payload])

    text_full = _join_pages(pages)
    try:
        Chunk.objects.filter(document=document).delete()
        Chunk.objects.bulk_create(
            [
                Chunk(
                    kb_id=document.kb_id,
                    document=document,
                    index=i,
                    page=chunk["page"],
                    text=chunk["text"],
                )
                for i, chunk in enumerate(chunks_payload)
            ],
            batch_size=500,
        )

        if backend.name == "milvus":
            # Idempotent re-ingest: drop stale vectors of this document,
            # then insert the fresh chunk vectors.
            chunks = list(
                Chunk.objects.filter(document=document).order_by("index")
            )
            backend.delete_document(document.kb, document.id)
            backend.upsert(
                document.kb,
                [
                    {
                        "chunk_id": chunk.id,
                        "document_id": document.id,
                        "page": chunk.page,
                        "text": chunk.text,
                        "embedding": embeddings[i],
                    }
                    for i, chunk in enumerate(chunks)
                ],
            )
        else:
            rag_engine.invalidate_kb_index(document.kb)
    except Exception as exc:
        logger.exception("文档向量化失败: %s", document.file_name)
        Chunk.objects.filter(document=document).delete()
        rag_engine.invalidate_kb_index(document.kb)
        msg = f"文档解析或向量化失败: {exc}"
        _mark_failed(document, msg)
        raise RuntimeError(msg) from exc

    document.text = text_full
    if not document.title:
        document.title = file_name or "未命名文档"
    document.status = Document.Status.READY
    document.save(update_fields=["text", "title", "status", "updated_at"])
    return len(chunks_payload)


def _join_pages(pages):
    """Join per-page texts into one audit text with page separators."""
    parts = []
    for page in pages:
        if page["page"] is not None:
            parts.append(f"\n\n--- 第 {page['page']} 页 ---\n\n{page['text']}")
        else:
            parts.append(page["text"])
    return "\n\n".join(parts).strip()


def _mark_failed(document, message):
    document.status = Document.Status.FAILED
    document.error = message
    document.save(update_fields=["status", "error", "updated_at"])


def retrieve(kb, query, top_k=None):
    """Multi-stage retrieval for ``kb``; returns a uniform result envelope.

    Envelope: ``{query, kb_id, knowledge_base, count, refused, threshold,
    best_score, backend, recall_count, results}`` where each result is
    ``{score, rerank_score, chunk_id, document_id, document_title,
    chunk_index, page, text}``. ``refused=True`` (with empty ``results``)
    when no chunk clears ``RAG_SIMILARITY_THRESHOLD``; callers must not
    forward a weak context to the LLM.
    """
    top_k = top_k or settings.RAG_DEFAULT_TOP_K
    base = {
        "query": query,
        "kb_id": kb.id,
        "knowledge_base": kb.name,
        "count": 0,
        "refused": True,
        "threshold": settings.RAG_SIMILARITY_THRESHOLD,
        "best_score": 0.0,
        "backend": None,
        "recall_count": 0,
        "results": [],
    }
    if not query or not query.strip():
        return base

    backend = vector_store.get_backend()
    base["backend"] = backend.name
    recall_n = min(
        int(top_k * settings.RAG_RECALL_MULTIPLIER), settings.RAG_RECALL_MAX
    )

    if backend.name == "milvus":
        query_vec = _embed_query(query)
        hits = backend.search(kb, query, query_vec, recall_n)
    else:
        hits = backend.search(kb, query, None, recall_n)
    base["recall_count"] = len(hits)
    if not hits:
        return base

    chunk_ids = [hit["chunk_id"] for hit in hits]
    chunks_by_id = {
        chunk.id: chunk
        for chunk in Chunk.objects.filter(kb=kb, id__in=chunk_ids)
        .select_related("document")
        .only(
            "id",
            "page",
            "text",
            "document_id",
            "document__title",
            "index",
        )
    }
    candidates = []
    for hit in hits:
        chunk = chunks_by_id.get(hit["chunk_id"])
        if chunk is None:
            continue
        candidates.append(
            {"chunk_id": chunk.id, "score": hit["score"], "text": chunk.text}
        )

    provider = settings.RAG_RERANK_PROVIDER
    if provider == "api" and candidates:
        reranked = reranker.rerank_api(query, candidates, top_k)
    else:
        reranked = reranker.rerank(query, candidates, top_k)

    results = []
    for candidate in reranked:
        chunk = chunks_by_id.get(candidate["chunk_id"])
        if chunk is None:
            continue
        results.append(
            {
                "score": candidate["score"],
                "rerank_score": candidate["rerank_score"],
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "document_title": chunk.document.title,
                "chunk_index": chunk.index,
                "page": chunk.page,
                "text": chunk.text,
            }
        )

    base["results"] = results
    base["count"] = len(results)
    base["best_score"] = (
        max(result["score"] for result in results) if results else 0.0
    )
    base["refused"] = base["best_score"] < settings.RAG_SIMILARITY_THRESHOLD
    if base["refused"]:
        # Keep the count honest but never expose weak context as answers.
        base["results"] = []
        base["count"] = 0
    return base
