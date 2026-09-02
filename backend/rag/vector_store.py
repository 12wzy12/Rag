"""Vector storage: Milvus (Lite) backend, with a memory backend fallback.

Storage model (business data in MySQL, vectors in Milvus):

- One Milvus collection per knowledge base: ``kb_{kb_id}_v{dim}`` (the dim
  suffix means switching embedding models with a different dimensionality
  transparently creates a fresh collection).
- Documents are upserted idempotently: ``delete document_id -> insert``.
- Only chunk vectors live in Milvus; the canonical chunk text / page metadata
  stays in the ``Chunk`` table and is joined back at retrieval time.

Milvus Lite notes:

- Milvus Lite 3.x is pure Python and runs on Windows (``pip install
  milvus-lite``). The local URI may be a file or a directory; the engine
  decides. It is single-process and the client is not thread-safe, so every
  operation is serialised through a module-level lock and a singleton client.
- When the Milvus backend cannot start (missing package, lock conflict,
  corrupt store) and ``RAG_VECTOR_FALLBACK_TO_MEMORY=1`` (default), the
  system degrades to :class:`MemoryBackend` (LlamaIndex disk persistence)
  and logs a warning. Chunk rows in MySQL remain the source of truth and the
  vectors can be rebuilt at any time by re-ingesting documents.
"""

import logging
import threading
from pathlib import Path

from django.conf import settings

from rag import rag_engine

logger = logging.getLogger(__name__)


class MilvusBackend:
    """Milvus Lite-backed vector store, one collection per knowledge base."""

    name = "milvus"

    def __init__(self, uri=None):
        self._uri = uri or settings.RAG_MILVUS_URI
        self._client_instance = None
        self._known_collections = set()
        # Guards client creation AND every collection operation (Milvus
        # Lite's embedded engine is not thread-safe).
        self._lock = threading.RLock()
        self._create_lock = threading.Lock()

    # ---- client plumbing ----

    def _client(self):
        if self._client_instance is not None:
            return self._client_instance
        with self._create_lock:
            if self._client_instance is not None:
                return self._client_instance
            try:
                import milvus_lite  # noqa: F401  ensure the engine is present
                from pymilvus import MilvusClient
            except ImportError as exc:
                raise RuntimeError(
                    "Milvus Lite 不可用：请执行 pip install milvus-lite"
                ) from exc
            # Local file/dir URIs need their parent to exist before the
            # embedded engine starts.
            if not self._uri.startswith("http"):
                Path(self._uri).parent.mkdir(parents=True, exist_ok=True)
            try:
                self._client_instance = MilvusClient(uri=self._uri)
            except Exception as exc:
                raise RuntimeError(
                    f"无法连接 Milvus Lite（{self._uri}）：{exc}"
                ) from exc
            logger.info("Milvus Lite 已连接：%s", self._uri)
            return self._client_instance

    def ping(self):
        """Probe availability (import + open). Raises RuntimeError on failure."""
        self._client()

    def close(self):
        """Release the embedded engine (file lock). Used by tests to
        simulate a process restart on the same data directory."""
        with self._lock:
            if self._client_instance is not None:
                try:
                    self._client_instance.close()
                except Exception:
                    pass
                self._client_instance = None
            self._known_collections.clear()

    @staticmethod
    def _collection_name(kb_id):
        return f"kb_{kb_id}_v{settings.RAG_EMBEDDING_DIM}"

    def _ensure_collection(self, kb_id):
        name = self._collection_name(kb_id)
        if name in self._known_collections:
            return
        client = self._client()
        if not client.has_collection(collection_name=name):
            from pymilvus import DataType

            schema = client.create_schema(auto_id=True)
            schema.add_field("id", DataType.INT64, is_primary=True)
            schema.add_field("chunk_id", DataType.INT64)
            schema.add_field("document_id", DataType.INT64)
            schema.add_field("kb_id", DataType.INT64)
            # Milvus has no clean nullable INT64 in every build; None pages
            # are stored as 0 and mapped back to None on output.
            schema.add_field("page", DataType.INT64)
            schema.add_field("text", DataType.VARCHAR, max_length=8192)
            schema.add_field(
                "embedding",
                DataType.FLOAT_VECTOR,
                dim=settings.RAG_EMBEDDING_DIM,
            )
            index_params = client.prepare_index_params()
            index_params.add_index(
                field_name="embedding",
                index_type="HNSW",
                metric_type="COSINE",
                params={"M": 16, "efConstruction": 256},
            )
            client.create_collection(
                collection_name=name, schema=schema, index_params=index_params
            )
            logger.info("创建 Milvus collection：%s", name)
        # Collections are created "loaded", but after the embedded engine
        # restarts (new process) they come back in the 'released' state and
        # search/query fail with "call load() before search". load() is
        # idempotent, so call it on every first use of a collection.
        try:
            client.load_collection(collection_name=name)
        except Exception as exc:
            logger.warning("加载 Milvus collection %s 失败：%s", name, exc)
        self._known_collections.add(name)

    # ---- operations (all under the module lock) ----

    def search(self, kb, query, query_vec, top_k):
        """Return ``[{chunk_id, score}]`` for the top-k nearest chunks.

        ``score`` is the COSINE distance reported by Milvus (bge-m3 vectors
        are normalised, so values fall in roughly [0, 1]).
        """
        if not query_vec:
            return []
        with self._lock:
            self._ensure_collection(kb.id)
            client = self._client()
            hits = client.search(
                collection_name=self._collection_name(kb.id),
                data=[query_vec],
                limit=int(top_k),
                output_fields=["chunk_id"],
                search_params={
                    "metric_type": "COSINE",
                    "params": {"ef": 128},
                },
            )
        results = []
        for hit in hits[0] if hits else []:
            try:
                chunk_id = int(hit["entity"]["chunk_id"])
            except (KeyError, TypeError):
                continue
            results.append(
                {
                    "chunk_id": chunk_id,
                    "score": round(float(hit["distance"]), 6),
                }
            )
        return results

    def upsert(self, kb, rows):
        """Insert vectors for a knowledge base's chunks (idempotent per
        document: call :meth:`delete_document` first or delete old chunks'
        rows by chunk_id before inserting new ones).

        ``rows``: ``[{chunk_id, document_id, page, text, embedding}]``.
        """
        if not rows:
            return
        with self._lock:
            self._ensure_collection(kb.id)
            client = self._client()
            entities = []
            for row in rows:
                entities.append(
                    {
                        "chunk_id": int(row["chunk_id"]),
                        "document_id": int(row["document_id"]),
                        "kb_id": kb.id,
                        "page": int(row["page"] or 0),
                        "text": row["text"][:8192],
                        "embedding": row["embedding"],
                    }
                )
            client.insert(
                collection_name=self._collection_name(kb.id), data=entities
            )

    def delete_document(self, kb, document_id):
        """Remove all vectors belonging to one document."""
        with self._lock:
            client = self._client()
            if not client.has_collection(
                collection_name=self._collection_name(kb.id)
            ):
                return
            client.delete(
                collection_name=self._collection_name(kb.id),
                filter=f"document_id == {int(document_id)}",
            )

    def clear_kb(self, kb_id):
        """Drop the whole knowledge base collection."""
        with self._lock:
            name = self._collection_name(kb_id)
            self._known_collections.discard(name)
            client = self._client()
            if client.has_collection(collection_name=name):
                client.drop_collection(collection_name=name)


class MemoryBackend:
    """LlamaIndex disk-persistence backend (no Milvus).

    Used by hermetic tests, and as an automatic fallback when Milvus Lite
    cannot start. The vector index is rebuilt lazily from the ``Chunk`` table
    on every content change (``rag_engine`` fingerprint logic).
    """

    name = "memory"

    def search(self, kb, query, query_vec, top_k):
        """Delegate to the LlamaIndex retriever; only scores are returned."""
        results = rag_engine.retrieve(kb, query, top_k=top_k)
        return [
            {"chunk_id": r["chunk_id"], "score": r["score"]} for r in results
        ]

    def upsert(self, kb, rows):
        # The index is rebuilt from Chunk rows, so no embedding is needed.
        rag_engine.invalidate_kb_index(kb)

    def delete_document(self, kb, document_id):
        rag_engine.invalidate_kb_index(kb)

    def clear_kb(self, kb_id):
        # No per-kb persisted data of our own; the KB cascade deletes chunks.
        pass

    def ping(self):
        return


_instances = {}
_instances_lock = threading.Lock()


def get_backend():
    """Return the configured vector backend (a singleton per backend type).

    When Milvus is configured but unusable, falls back to memory when
    ``RAG_VECTOR_FALLBACK_TO_MEMORY=1``; otherwise raises ``RuntimeError``.
    """
    backend_key = settings.RAG_VECTOR_BACKEND
    with _instances_lock:
        cached = _instances.get(backend_key)
        if cached is not None:
            return cached

    if backend_key == "memory":
        backend = MemoryBackend()
    elif backend_key == "milvus":
        backend = MilvusBackend()
        try:
            backend.ping()
        except RuntimeError as exc:
            if settings.RAG_VECTOR_FALLBACK_TO_MEMORY:
                logger.warning(
                    "Milvus 后端不可用，已降级为 memory 后端：%s", exc
                )
                backend = MemoryBackend()
            else:
                raise
    else:
        raise RuntimeError(f"未知的向量后端: {backend_key}")

    with _instances_lock:
        _instances[backend_key] = backend
    return backend
