"""LlamaIndex-backed RAG engine.

Every retrieval path here goes through the LlamaIndex framework:

- Embeddings: ``OllamaEmbedding`` against a local Ollama ``bge-m3`` model by
  default (multilingual, good for Chinese), with a dependency-free
  ``LexicalEmbedding`` fallback for environments without Ollama / for tests.
- Indexing: ``VectorStoreIndex`` built from per-knowledge-base chunks, using
  ``TextNode(id_=<chunk_pk>, text=<chunk_text>)`` nodes.
- Persistence: each knowledge base's index + a content fingerprint are
  persisted to ``RAG_INDEX_DIR/<kb_id>/`` so a query does not re-embed the
  whole corpus on every call; the index is rebuilt only when the chunk set
  changes.
- Retrieval: ``index.as_retriever(similarity_top_k=...)``.
"""

import hashlib
import json
import shutil
from pathlib import Path

from django.conf import settings
from django.db.models import Count, Max
from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core import load_index_from_storage
from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.core.schema import TextNode
from llama_index.embeddings.ollama import OllamaEmbedding

from rag.models import Chunk
from rag.tokenizer import tokenize


class LexicalEmbedding(BaseEmbedding):
    """Deterministic, dependency-free embedding: bag-of-tokens projected onto
    a fixed-dimension vector via hashing. Used as the Ollama fallback and in
    hermetic tests; not the default in production."""

    def __init__(self, dim=1024, **kwargs):
        super().__init__(**kwargs)
        self._dim = int(dim)

    @staticmethod
    def _hash(token, dim):
        return int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16) % dim

    def _embed(self, text):
        import numpy as np

        vec = np.zeros(self._dim, dtype=np.float32)
        for tok in tokenize(text):
            vec[self._hash(tok, self._dim)] += 1.0
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec.tolist()

    def _get_query_embedding(self, query):
        return self._embed(query)

    def _get_text_embedding(self, text):
        return self._embed(text)

    def _get_text_embeddings(self, texts):
        return [self._embed(t) for t in texts]

    async def _aget_query_embedding(self, query):
        return self._embed(query)

    async def _aget_text_embedding(self, text):
        return self._embed(text)


_embed_model_instance = None


def get_embed_model():
    """Return the configured (and memoised) embedding model."""
    global _embed_model_instance
    if _embed_model_instance is not None:
        return _embed_model_instance

    provider = settings.RAG_EMBEDDING_PROVIDER
    if provider == "lexical":
        _embed_model_instance = LexicalEmbedding(dim=settings.RAG_EMBEDDING_DIM)
    else:
        _embed_model_instance = OllamaEmbedding(
            model_name=settings.RAG_EMBEDDING_MODEL,
            base_url=settings.RAG_OLLAMA_BASE_URL,
            ollama_additional_kwargs={
                "keep_alive": settings.RAG_OLLAMA_KEEP_ALIVE
            },
        )
    return _embed_model_instance


def _persist_dir(kb_id):
    return Path(settings.RAG_INDEX_DIR) / f"kb_{kb_id}"


def _fingerprint(kb):
    """Cheap content fingerprint: rebuilding triggers when the chunk set
    changes (count / max id / newest document edit)."""
    if not Chunk.objects.filter(kb=kb).exists():
        return "empty"
    stats = Chunk.objects.filter(kb=kb).aggregate(
        count=Count("id"),
        max_id=Max("id"),
        doc=Max("document__updated_at"),
    )
    payload = {
        "count": stats["count"],
        "max_id": stats["max_id"],
        "doc_updated": str(stats["doc"]),
        "model": settings.RAG_EMBEDDING_MODEL,
        "dim": settings.RAG_EMBEDDING_DIM,
    }
    return hashlib.sha1(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()


def get_index(kb):
    """Return the (possibly rebuilt) vector index for a knowledge base, or
    ``None`` when it has no chunks."""
    if not Chunk.objects.filter(kb=kb).exists():
        return None

    fp = _fingerprint(kb)
    persist_dir = _persist_dir(kb.id)
    meta_path = persist_dir / "meta.json"

    if persist_dir.exists() and meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta.get("fingerprint") == fp:
                storage = StorageContext.from_defaults(persist_dir=str(persist_dir))
                return load_index_from_storage(storage)
        except Exception:
            # Fall through and rebuild from a corrupt/partial store.
            pass

    nodes = [
        TextNode(text=chunk.text, id_=str(chunk.id))
        for chunk in Chunk.objects.filter(kb=kb).order_by("id")
    ]
    index = VectorStoreIndex(
        nodes, embed_model=get_embed_model(), show_progress=False
    )
    persist_dir.mkdir(parents=True, exist_ok=True)
    index.storage_context.persist(persist_dir=str(persist_dir))
    meta_path.write_text(
        json.dumps({"fingerprint": fp}, ensure_ascii=False), encoding="utf-8"
    )
    return index


def retrieve(kb, query, top_k=None):
    """Return the top-k chunks of ``kb`` matching ``query`` via LlamaIndex.

    Each result: ``{score, chunk_id, document_id, document_title,
    chunk_index, page, text}``, ordered by relevance (descending).
    """
    if not query or not query.strip():
        return []
    if top_k is None:
        top_k = settings.RAG_DEFAULT_TOP_K

    index = get_index(kb)
    if index is None:
        return []

    retriever = index.as_retriever(similarity_top_k=int(top_k))
    nodes = retriever.retrieve(query)

    chunks_by_id = {
        str(chunk.id): chunk
        for chunk in Chunk.objects.filter(kb=kb, id__in=[int(n.node_id) for n in nodes])
    }

    results = []
    for node in nodes:
        chunk = chunks_by_id.get(node.node_id)
        if chunk is None:
            continue
        results.append(
            {
                "score": round(float(node.score) if node.score is not None else 0.0, 6),
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "document_title": chunk.document.title,
                "chunk_index": chunk.index,
                "page": chunk.page,
                "text": chunk.text,
            }
        )
    return results


def invalidate_kb_index(kb):
    """Drop a persisted index so the next query rebuilds it (used after
    document deletion / re-ingestion)."""
    persist_dir = _persist_dir(kb.id)
    if persist_dir.exists():
        shutil.rmtree(persist_dir, ignore_errors=True)
