"""Tests for the LlamaIndex-backed RAG pipeline.

Retrieval tests use the dependency-free ``LexicalEmbedding`` fallback so the
suite is hermetic (no Ollama server required) while still exercising the real
LlamaIndex ``VectorStoreIndex`` + retriever code path.
"""

import shutil
import tempfile

from django.test import TestCase, override_settings

from rag import rag_engine
from rag.models import Document, KnowledgeBase
from rag.services import extract_text, ingest_document, retrieve
from rag.tokenizer import tokenize

TEST_SETTINGS = {
    "RAG_EMBEDDING_PROVIDER": "lexical",
    "RAG_EMBEDDING_DIM": 512,
    "RAG_INDEX_DIR": tempfile.mkdtemp(prefix="rag_test_"),
    "RAG_CHUNK_SIZE": 200,
    "RAG_CHUNK_OVERLAP": 40,
}


class TokenizerTests(TestCase):
    def test_cjk_bigrams(self):
        self.assertEqual(tokenize("机器学习"), ["机器", "器学", "学习"])

    def test_latin_words_lowercased(self):
        self.assertIn("rag", tokenize("RAG Backend"))

    def test_mixed(self):
        toks = tokenize("用BM25做检索")
        self.assertIn("bm25", toks)
        self.assertIn("检索", toks)


@override_settings(**TEST_SETTINGS)
class RagEngineTests(TestCase):
    def setUp(self):
        rag_engine._embed_model_instance = None  # pick up lexical embedding
        self.addCleanup(
            shutil.rmtree, TEST_SETTINGS["RAG_INDEX_DIR"], ignore_errors=True
        )

    def _make_kb(self, docs):
        kb = KnowledgeBase.objects.create(name="测试库")
        for i, text in enumerate(docs):
            doc = Document.objects.create(
                kb=kb,
                title=f"d{i}",
                file_name=f"d{i}.txt",
                content_type="text/plain",
                size=len(text),
            )
            ingest_document(doc, text.encode("utf-8"), "text/plain", f"d{i}.txt")
        return kb

    def test_ingest_chunks_and_index_rebuildable(self):
        kb = self._make_kb(["机器学习与自然语言处理的研究进展"])
        self.assertEqual(Document.objects.filter(kb=kb).count(), 1)
        self.assertGreaterEqual(kb.chunks.count(), 1)

    def test_relevant_chunk_ranked_first(self):
        kb = self._make_kb(
            [
                "智能问答模块调用大语言模型生成回答，支持配置模型接口与API密钥。",
                "本产品是一款面向企业的知识管理平台，支持文档上传与全文检索。",
            ]
        )
        results = retrieve(kb, "大语言模型如何生成智能问答回答", top_k=2)
        self.assertEqual(len(results), 2)
        # The LLM/智能问答 chunk must rank above the general platform chunk.
        targeted = next(r for r in results if r["document_title"] == "d0")
        general = next(r for r in results if r["document_title"] == "d1")
        self.assertGreater(targeted["score"], general["score"])

    def test_retrieval_returns_no_scores_for_empty_kb(self):
        kb = KnowledgeBase.objects.create(name="空库")
        self.assertEqual(retrieve(kb, "任何查询"), [])

    def test_unsupported_format_marks_failed(self):
        kb = KnowledgeBase.objects.create(name="另库")
        doc = Document.objects.create(kb=kb, title="d", file_name="d.pdf")
        with self.assertRaises(ValueError):
            extract_text(b"%PDF-x", "application/pdf", "d.pdf")
        with self.assertRaises(ValueError):
            ingest_document(doc, b"%PDF-x", "application/pdf", "d.pdf")
        doc.refresh_from_db()
        self.assertEqual(doc.status, Document.Status.FAILED)
        self.assertIn("不支持的文档格式", doc.error)
