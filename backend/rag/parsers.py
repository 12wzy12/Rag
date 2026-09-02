"""Document parsing: raw file bytes -> list of (page, text) segments.

Supported formats:

- PDF (``application/pdf``): extracted per page with PyMuPDF; each page keeps
  its 1-based page number so downstream chunks can carry source metadata.
- Word (``.docx``): extracted with python-docx; no page information is
  available from the format itself (``page=None``).
- Plain-text formats (txt/md/csv/json/html/xml): decoded as before,
  ``page=None``.

Text is lightly cleaned per page/segment before chunking (see
:func:`_clean_text`): normalise line endings, strip control characters and
collapse long blank runs. Binary formats we cannot parse raise ``ValueError``
with a readable Chinese message.
"""

import re
from html import unescape
from io import BytesIO

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

_DOCX_MIME = (
    "application/vnd.openxmlformats-officedocument."
    "wordprocessingml.document"
)

_HTML_TAG = re.compile(r"<[^>]+>")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_BLANK_RUN = re.compile(r"\n{3,}")


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


def _clean_text(text):
    """Normalise line endings, drop control characters, collapse blank runs."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _CONTROL.sub("", text)
    text = _BLANK_RUN.sub("\n\n", text)
    return text.strip()


def _extract_pdf(raw_bytes):
    """Extract per-page text from a PDF using PyMuPDF (import name ``fitz``).

    Raises ``ValueError`` when the bytes are not a readable PDF.
    """
    try:
        import fitz
    except ImportError as exc:
        raise ValueError("未安装 PDF 解析库（pip install PyMuPDF）") from exc

    try:
        doc = fitz.open(stream=raw_bytes, filetype="pdf")
    except Exception as exc:  # fitz.FileDataError / RuntimeError for garbage
        raise ValueError(f"无法解析 PDF 文件: {exc}") from exc

    pages = []
    try:
        for index, page in enumerate(doc):
            text = _clean_text(page.get_text("text"))
            if text:
                pages.append({"page": index + 1, "text": text})
    finally:
        doc.close()
    if not pages:
        raise ValueError("PDF 未包含可提取的文本内容（可能是扫描件）")
    return pages


def _extract_docx(raw_bytes):
    """Extract text from a .docx (python-docx); page info is unavailable."""
    try:
        from docx import Document
    except ImportError as exc:
        raise ValueError("未安装 Word 解析库（pip install python-docx）") from exc

    try:
        doc = Document(BytesIO(raw_bytes))
        paragraphs = [p.text for p in doc.paragraphs]
    except Exception as exc:
        raise ValueError(f"无法解析 Word 文件: {exc}") from exc

    text = _clean_text("\n".join(paragraphs))
    if not text:
        raise ValueError("Word 文档未包含可提取的文本内容")
    return [{"page": None, "text": text}]


def extract_text(raw_bytes, content_type, file_name):
    """Return ``[{"page": int|None, "text": str}, ...]`` for an uploaded file.

    Raises ``ValueError`` with a readable message for unsupported or
    unreadable formats.
    """
    ctype = (content_type or "").lower()
    name = (file_name or "").lower()

    # Binary formats first, so they never fall through to text decoding.
    if ctype == "application/pdf" or name.endswith(".pdf"):
        return _extract_pdf(raw_bytes)
    if ctype == _DOCX_MIME or name.endswith(".docx"):
        return _extract_docx(raw_bytes)

    if ctype in _TEXT_TYPES or ctype.startswith("text/"):
        text = _decode(raw_bytes)
        if ctype in ("text/html", "text/xml", "application/xml"):
            text = _strip_html(text)
        return [{"page": None, "text": _clean_text(text)}]
    if name.endswith((".txt", ".md", ".markdown", ".csv", ".log", ".json")):
        return [{"page": None, "text": _clean_text(_decode(raw_bytes))}]
    if name.endswith((".html", ".htm", ".xml")):
        return [
            {"page": None, "text": _clean_text(_strip_html(_decode(raw_bytes)))}
        ]

    raise ValueError(
        f"不支持的文档格式: {content_type or file_name or '未知'}"
        "（支持 PDF / Word(docx) / txt / md / csv / json / html / xml）"
    )
