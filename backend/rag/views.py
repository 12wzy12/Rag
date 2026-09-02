from django.conf import settings
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from rag import llm as llm_service
from rag.models import Chunk, Document, KnowledgeBase
from rag.serializers import (
    ChunkSerializer,
    DocumentSerializer,
    KnowledgeBaseSerializer,
    SearchSerializer,
)
from rag.services import ingest_document, retrieve


class KnowledgeBaseViewSet(viewsets.ModelViewSet):
    """Knowledge base (collection of documents sharing one index)."""

    queryset = KnowledgeBase.objects.all()
    serializer_class = KnowledgeBaseSerializer
    lookup_field = "pk"

    @action(detail=True, methods=["post"])
    def search(self, request, pk=None):
        """Retrieve top-k chunks from a knowledge base for a query."""
        kb = self.get_object()
        ser = SearchSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        top_k = ser.validated_data.get("top_k", settings.RAG_DEFAULT_TOP_K)
        results = retrieve(kb, ser.validated_data["query"], top_k=top_k)
        return Response(
            {
                "query": ser.validated_data["query"],
                "knowledge_base": kb.name,
                "count": len(results),
                "results": results,
            }
        )

    @action(detail=True, methods=["post"])
    def answer(self, request, pk=None):
        """Retrieve context, then generate an answer with the configured LLM.

        Only available when RAG_LLM_BASE_URL / RAG_LLM_API_KEY are configured;
        otherwise returns 400 so callers fall back to ``search``.
        """
        kb = self.get_object()
        ser = SearchSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        top_k = ser.validated_data.get("top_k", settings.RAG_DEFAULT_TOP_K)
        results = retrieve(kb, ser.validated_data["query"], top_k=top_k)

        if not results:
            return Response(
                {"query": ser.validated_data["query"], "answer": "根据现有知识库无法回答", "results": []}
            )
        if not llm_service.is_configured():
            return Response(
                {"detail": "未配置模型服务（RAG_LLM_BASE_URL / RAG_LLM_API_KEY），请使用 /search 接口"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            answer, n = llm_service.generate_answer(
                ser.validated_data["query"], results
            )
        except RuntimeError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(
            {
                "query": ser.validated_data["query"],
                "answer": answer,
                "used_chunks": n,
                "results": results,
            }
        )

    @action(detail=True, methods=["get"])
    def documents(self, request, pk=None):
        """List documents belonging to a knowledge base."""
        kb = self.get_object()
        docs = Document.objects.filter(kb=kb)
        ser = DocumentSerializer(docs, many=True)
        return Response(
            {
                "knowledge_base": kb.name,
                "count": docs.count(),
                "documents": ser.data,
            }
        )


class DocumentViewSet(viewsets.ModelViewSet):
    """Documents: upload a file, ingest (parse+chunk+index) it."""

    queryset = Document.objects.all()
    serializer_class = DocumentSerializer

    def create(self, request, *args, **kwargs):
        file_obj = request.FILES.get("file")
        if not file_obj:
            return Response(
                {"detail": "缺少上传文件字段 'file'（multipart/form-data）"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if file_obj.size > settings.RAG_MAX_UPLOAD_BYTES:
            return Response(
                {"detail": f"文件超过大小限制 {settings.RAG_MAX_UPLOAD_BYTES} 字节"},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )

        kb = request.data.get("kb")
        if not kb:
            return Response(
                {"detail": "缺少知识库字段 'kb'（KnowledgeBase 的 id）"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            knowledge_base = KnowledgeBase.objects.get(pk=kb)
        except KnowledgeBase.DoesNotExist:
            return Response(
                {"detail": f"知识库 {kb} 不存在"},
                status=status.HTTP_404_NOT_FOUND,
            )

        document = Document.objects.create(
            kb=knowledge_base,
            title=request.data.get("title") or file_obj.name,
            file_name=file_obj.name,
            content_type=file_obj.content_type or "",
            size=file_obj.size,
        )

        raw = file_obj.read()
        try:
            chunk_total = ingest_document(
                document, raw, file_obj.content_type, file_obj.name
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc), "document": DocumentSerializer(document).data},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "message": "文档解析完成",
                "chunk_count": chunk_total,
                "document": DocumentSerializer(document).data,
            },
            status=status.HTTP_201_CREATED,
        )

    def destroy(self, request, *args, **kwargs):
        from rag import rag_engine

        instance = self.get_object()
        kb = instance.kb
        # Cascade removes chunks via FK.
        instance.delete()
        # Drop the persisted index so the next query rebuilds without the
        # deleted document's chunks.
        rag_engine.invalidate_kb_index(kb)
        return Response(
            {
                "message": "已删除文档",
                "deleted_documents": 1,
                "knowledge_base_id": kb.id,
            }
        )


class ChunkViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only view into indexed chunks (debugging / audit)."""

    queryset = Chunk.objects.select_related("document").all()
    serializer_class = ChunkSerializer
