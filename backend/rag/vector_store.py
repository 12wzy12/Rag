"""向量存储：Milvus (Lite) 后端，附带内存后端回退方案。

存储模型（业务数据在 MySQL，向量在 Milvus）：

- 每个知识库对应一个 Milvus collection：``kb_{kb_id}_v{dim}``（维度后缀使
  切换到不同维度的嵌入模型时会透明地创建全新 collection）。
- 文档幂等 upsert：``delete document_id -> insert``。
- 只有分块向量存放在 Milvus；分块正文与页码元数据的权威数据保存在
  ``Chunk`` 表中，检索时再关联取回。

Milvus Lite 说明：

- Milvus Lite 3.x 为纯 Python 实现，可在 Windows 上运行（``pip install
  milvus-lite``）。本地 URI 可以是文件或目录，由引擎自行判断。它只支持
  单进程，客户端亦非线程安全，因此所有操作通过模块级锁与单例客户端串行
  执行。
- 当 Milvus 后端无法启动（缺少依赖包、锁冲突、存储损坏）且
  ``RAG_VECTOR_FALLBACK_TO_MEMORY=1``（默认值）时，系统降级为
  :class:`MemoryBackend`（LlamaIndex 磁盘持久化）并记录警告日志。MySQL
  中的 Chunk 记录始终是数据真相来源，可随时重新导入文档以重建向量。
"""

import logging
import threading
from pathlib import Path

from django.conf import settings

from rag import rag_engine

logger = logging.getLogger(__name__)


class MilvusBackend:
    """基于 Milvus Lite 的向量存储；每个知识库对应一个 collection。"""

    name = "milvus"

    def __init__(self, uri=None):
        self._uri = uri or settings.RAG_MILVUS_URI
        self._client_instance = None
        self._known_collections = set()
        # 同时保护客户端创建与所有 collection 操作
        # （Milvus Lite 内嵌引擎并非线程安全）。
        self._lock = threading.RLock()
        self._create_lock = threading.Lock()

    # ---- 客户端连接管理 ----

    def _client(self):
        if self._client_instance is not None:
            return self._client_instance
        with self._create_lock:
            if self._client_instance is not None:
                return self._client_instance
            try:
                import milvus_lite  # noqa: F401  确保引擎已安装
                from pymilvus import MilvusClient
            except ImportError as exc:
                raise RuntimeError(
                    "Milvus Lite 不可用：请执行 pip install milvus-lite"
                ) from exc
            # 本地文件/目录形式的 URI 需先确保父目录存在，
            # 内嵌引擎才能正常启动。
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
        """探测可用性（导入并打开）。失败时抛出 RuntimeError。"""
        self._client()

    def close(self):
        """释放内嵌引擎（文件锁）。测试中用于在同一数据目录上
        模拟进程重启。"""
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
            # 并非所有 Milvus 版本都支持可空的 INT64 字段；None 页码
            # 以 0 存储，输出时再映射回 None。
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
        # collection 创建后处于 "loaded" 状态，但内嵌引擎重启（新进程）后
        # 会回到 'released' 状态，此时 search/query 会因 "call load() before
        # search" 而失败。load() 是幂等的，因此每次首次使用某 collection
        # 时都调用一次。
        try:
            client.load_collection(collection_name=name)
        except Exception as exc:
            logger.warning("加载 Milvus collection %s 失败：%s", name, exc)
        self._known_collections.add(name)

    # ---- 操作方法（全部在模块锁保护下） ----

    def search(self, kb, query, query_vec, top_k):
        """返回最相似的 top-k 个分块：``[{chunk_id, score}]``。

        ``score`` 为 Milvus 返回的 COSINE 距离（bge-m3 向量已归一化，
        取值大致落在 [0, 1]）。
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
        """为知识库的分块插入向量（对单个文档幂等：需先调用
        :meth:`delete_document`，或先按 chunk_id 删除旧分块记录，再插入
        新记录）。

        ``rows``：``[{chunk_id, document_id, page, text, embedding}]``。
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
        """删除属于某一文档的全部向量。"""
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
        """删除整个知识库对应的 collection。"""
        with self._lock:
            name = self._collection_name(kb_id)
            self._known_collections.discard(name)
            client = self._client()
            if client.has_collection(collection_name=name):
                client.drop_collection(collection_name=name)


class MemoryBackend:
    """LlamaIndex 磁盘持久化后端（不使用 Milvus）。

    用于封闭性测试，并在 Milvus Lite 无法启动时作为自动回退方案。向量
    索引在内容变化时按需从 ``Chunk`` 表重建（由 ``rag_engine`` 的
    fingerprint 逻辑触发）。
    """

    name = "memory"

    def search(self, kb, query, query_vec, top_k):
        """委托给 LlamaIndex 检索器执行；仅返回分数。"""
        results = rag_engine.retrieve(kb, query, top_k=top_k)
        return [
            {"chunk_id": r["chunk_id"], "score": r["score"]} for r in results
        ]

    def upsert(self, kb, rows):
        # 索引由 Chunk 记录重建，因此无需写入嵌入向量。
        rag_engine.invalidate_kb_index(kb)

    def delete_document(self, kb, document_id):
        rag_engine.invalidate_kb_index(kb)

    def clear_kb(self, kb_id):
        # 本后端没有按知识库持久化的自有数据；知识库级联删除会清理分块。
        pass

    def ping(self):
        return


_instances = {}
_instances_lock = threading.Lock()


def get_backend():
    """返回配置的向量后端（每种后端类型保持单例）。

    配置为 Milvus 但无法使用时，若 ``RAG_VECTOR_FALLBACK_TO_MEMORY=1``
    则回退为 memory 后端；否则抛出 ``RuntimeError``。
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
