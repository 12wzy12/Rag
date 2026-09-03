"""分块：将页（或段）文本切分为带页码元数据的 LlamaIndex 分块。

每页/每段生成一个 LlamaIndex ``Document``，页码 ``page`` 存入其元数据；
``SentenceSplitter`` 随后一次性切分整篇文档。跨页边界的分块继承其起始页
的元数据——这是有意为之：来源引用应指向读者需要打开的那一段。
"""

from django.conf import settings
from llama_index.core import Document as IndexDocument
from llama_index.core.node_parser import SentenceSplitter


def chunk_pages(pages, chunk_size=None, chunk_overlap=None):
    """将 ``[{"page": int|None, "text": str}]`` 切分为分块。

    返回可直接持久化的 ``[{"page": int|None, "text": str}]`` 列表。
    """
    if chunk_size is None:
        chunk_size = settings.RAG_CHUNK_SIZE
    if chunk_overlap is None:
        chunk_overlap = settings.RAG_CHUNK_OVERLAP

    splitter = SentenceSplitter.from_defaults(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    documents = []
    for segment in pages:
        if not segment["text"]:
            continue
        # 仅在存在真实页码时附加元数据，
        # 使 llama-index 节点元数据不出现 None 值。
        metadata = (
            {"page": int(segment["page"])} if segment["page"] else {}
        )
        documents.append(
            IndexDocument(text=segment["text"], metadata=metadata)
        )
    nodes = splitter.get_nodes_from_documents(documents)
    return [
        {
            "page": node.metadata.get("page"),
            "text": node.get_content(),
        }
        for node in nodes
    ]


def chunk_text(text, chunk_size=None, chunk_overlap=None):
    """将一段纯文本切分为分块（页码元数据为 None）。"""
    return chunk_pages(
        [{"page": None, "text": text}],
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
