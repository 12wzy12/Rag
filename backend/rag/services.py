"""RAG ingestion and retrieval services (LlamaIndex-backed).

Ingestion: decode a raw uploaded file to plain text, split it into chunks
with LlamaIndex's ``SentenceSplitter``, persist the chunks, and invalidate
the knowledge base's vector index so the next query rebuilds it.

Retrieval: delegated to :mod:`rag.rag_engine`, which builds and queries a
LlamaIndex ``VectorStoreIndex`` per knowledge base.
"""

import re
from html import unescape

from django.conf import settings
from llama_index.core import Document as IndexDocument
from llama_index.core.node_parser import SentenceSplitter

from rag import rag_engine
from rag.models import Chunk, Document

# ---- File parsing (text-oriented formats only, no binary deps) ----

_TEXT_TYPES = {
    "text/plain",
    "text/markdown",
    "text/csv",
    "text/html",
    "text/xml",
    "application/xml",
    "application/json",
    "application/javascript",
    "application/x-javascript",
    "text/javascript",
    "text/css",
}

_HTML_TAG = re.compile(r"<[^>]+>")


def _decode(raw_bytes):
    for enc in ("utf-8-sig", "utf-8", "gb18030", "gbk", "latin-1"):
        try:
            return raw_bytes.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw_bytes.decode("latin-1", errors="replace")


def _strip_html(text):
    text = _HTML_TAG.sub(" ", text)
    return re.sub(r"\s+", " ", unescape(text)).strip()


def extract_text(raw_bytes, content_type, file_name):
    """Return (plain_text, effective_content_type) for an uploaded file.

    Raises ``ValueError`` for binary formats we cannot parse without
    external libraries (PDF, Word, images, archives...).
    """
    ctype = (content_type or "").lower()
    name = (file_name or "").lower()

    if ctype in _TEXT_TYPES or ctype.startswith("text/"):
        return _decode(raw_bytes), ctype

    if name.endswith((".txt", ".md", ".markdown", ".csv", ".log")):
        return _decode(raw_bytes), ctype
    if name.endswith((".json",)):
        return _decode(raw_bytes), ctype
    if name.endswith((".html", ".htm")):
        return _strip_html(_decode(raw_bytes)), ctype
    if name.endswith((".xml",)):
        return _strip_html(_decode(raw_bytes)), ctype

    raise ValueError(
        f"不支持的文档格式: {content_type or file_name or '未知'}"
        "（仅支持纯文本类格式 txt/md/csv/json/html；PDF/Word 需额外安装解析库）"
    )


def _chunk_text(text):
    """Split text into chunks using LlamaIndex's sentence-aware splitter."""
    splitter = SentenceSplitter.from_defaults(
        chunk_size=settings.RAG_CHUNK_SIZE,
        chunk_overlap=settings.RAG_CHUNK_OVERLAP,
    )
    nodes = splitter.get_nodes_from_documents([IndexDocument(text=text)])
    return [node.get_content() for node in nodes]


def ingest_document(document, raw_bytes, content_type, file_name):
    """Extract, chunk and index a :class:`Document` via LlamaIndex.

    Replaces any previously indexed chunks for the same document and
    invalidates the knowledge base vector index for a rebuild.
    """
    document.status = Document.Status.PARSING
    document.error = ""
    document.save(update_fields=["status", "error", "updated_at"])
    try:
        text, ctype = extract_text(raw_bytes, content_type, file_name)
    except ValueError as exc:
        document.status = Document.Status.FAILED
        document.error = str(exc)
        document.save(update_fields=["status", "error", "updated_at"])
        raise

    chunk_texts = _chunk_text(text)

    Chunk.objects.filter(document=document).delete()
    Chunk.objects.bulk_create(
        [
            Chunk(kb_id=document.kb_id, document=document, index=i, text=chunk)
            for i, chunk in enumerate(chunk_texts)
        ],
        batch_size=500,
    )
    rag_engine.invalidate_kb_index(document.kb)

    document.text = text
    document.status = Document.Status.READY
    if not document.title:
        document.title = file_name or "未命名文档"
    document.save(update_fields=["text", "title", "status", "updated_at"])
    return len(chunk_texts)


def retrieve(kb, query, top_k=None):
    """Return the top-k chunks of ``kb`` matching ``query`` (LlamaIndex)."""
    return rag_engine.retrieve(kb, query, top_k=top_k)
