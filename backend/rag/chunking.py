"""Chunking: page (or segment) texts -> LlamaIndex chunks with page metadata.

Each page/segment becomes one LlamaIndex ``Document`` carrying ``page`` in its
metadata; ``SentenceSplitter`` then splits the whole book at once. Chunks that
span a page boundary inherit the metadata of the page they start in — this is
deliberate: the source citation points at the segment the reader should open.
"""

from django.conf import settings
from llama_index.core import Document as IndexDocument
from llama_index.core.node_parser import SentenceSplitter


def chunk_pages(pages, chunk_size=None, chunk_overlap=None):
    """Split ``[{"page": int|None, "text": str}]`` into chunks.

    Returns ``[{"page": int|None, "text": str}]`` ready for persistence.
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
        # Only attach metadata when there is a real page number, keeping
        # llama-index node metadata free of None values.
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
    """Split a single plain text into chunks (page metadata = None)."""
    return chunk_pages(
        [{"page": None, "text": text}],
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
