"""RAG 文档导入与检索服务。

导入流水线（每份上传的文档）：

    文件字节 -> :func:`parsers.extract_text`（逐页提取，PDF 带页码）
    -> :func:`chunking.chunk_pages`（LlamaIndex SentenceSplitter）
    -> MySQL 中的 ``Chunk`` 记录（业务数据）-> 批量嵌入（默认经 Ollama
    使用 BGE-M3）-> 向量 upsert 至 Milvus（向量数据）。

检索流水线（多阶段，按查询执行）：

    查询嵌入 -> 第一阶段：Milvus 向量召回（top_k * 召回倍数，设有上限）
    -> 第二阶段：:func:`reranker.rerank` 混合重排 -> 附加文档元数据
    -> 相关度闸门：当没有任何分块达到 ``RAG_SIMILARITY_THRESHOLD`` 时，
    查询被 *拒绝*（``refused=True``，结果为空），调用方绝不会把弱相关
    上下文交给 LLM。
"""

import logging

from django.conf import settings

from rag import chunking, parsers, rag_engine, reranker, vector_store
from rag.models import Chunk, Document

logger = logging.getLogger(__name__)


def _embed_texts(texts):
    """用配置的嵌入模型（默认经 Ollama 调用 BGE-M3）批量嵌入文本。
    服务调用失败时抛出 ``RuntimeError``。"""
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
    """解析、分块并为 :class:`Document` 建立向量索引。

    会替换该文档此前已索引的所有分块。成功后文档标记为 ``ready``；
    失败时标记为 ``failed`` 并附可读错误信息（不支持的格式抛出
    ``ValueError``，其余情况抛出 ``RuntimeError``，由调用方以 503 返回）。
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

    # 向量后端为 Milvus：必须在写入任何分块记录前先完成嵌入，
    # 这样嵌入服务中断也不会留下半成品状态。
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
            # 幂等重导：先删除该文档的过期向量，
            # 再插入新生成的分块向量。
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
    """将各页文本按页码分隔拼接为一份存档文本。"""
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
    """对 ``kb`` 执行多阶段检索；返回统一的结果信封。

    信封结构：``{query, kb_id, knowledge_base, count, refused, threshold,
    best_score, backend, recall_count, results}``，其中每条结果为
    ``{score, rerank_score, chunk_id, document_id, document_title,
    chunk_index, page, text}``。当没有任何分块达到
    ``RAG_SIMILARITY_THRESHOLD`` 时 ``refused=True``（且 ``results`` 为空）；
    调用方不得把弱相关上下文转发给 LLM。
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
        # 保持计数如实，但绝不把弱相关上下文当作答案返回。
        base["results"] = []
        base["count"] = 0
    return base
