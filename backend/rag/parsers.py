"""文档解析：原始文件字节 -> 页文本 (page, text) 段列表。

支持的格式：

- PDF（``application/pdf``）：用 PyMuPDF 按页提取文本；每页保留从 1 起始的
  页码，使下游分块能携带来源元数据。
- Word（``.docx``）：用 python-docx 提取文本；该格式本身不提供页码信息
  （``page=None``）。
- 纯文本格式（txt/md/csv/json/html/xml）：按文本解码，``page=None``。

文本在分块前会按页/段做轻度清洗（见 :func:`_clean_text`）：统一换行符、
剔除控制字符并压缩过长的空行序列。无法解析的二进制格式抛出带可读中文提示
的 ``ValueError``。
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
    """统一换行符，剔除控制字符，压缩连续空行。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _CONTROL.sub("", text)
    text = _BLANK_RUN.sub("\n\n", text)
    return text.strip()


def _extract_pdf(raw_bytes):
    """使用 PyMuPDF（导入名 ``fitz``）逐页提取 PDF 文本。

    当字节数据不是可读的 PDF 时抛出 ``ValueError``。
    """
    try:
        import fitz
    except ImportError as exc:
        raise ValueError("未安装 PDF 解析库（pip install PyMuPDF）") from exc

    try:
        doc = fitz.open(stream=raw_bytes, filetype="pdf")
    except Exception as exc:  # fitz.FileDataError / RuntimeError 等无效内容异常
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
    """从 .docx 提取文本（python-docx）；无页码信息。"""
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
    """返回上传文件的 ``[{"page": int|None, "text": str}, ...]`` 段列表。

    对不支持或无法读取的格式，抛出带可读提示的 ``ValueError``。
    """
    ctype = (content_type or "").lower()
    name = (file_name or "").lower()

    # 二进制格式优先处理，避免落入文本解码分支。
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
