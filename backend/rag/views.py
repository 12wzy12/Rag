import logging

from django.conf import settings
from django.http import StreamingHttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from rag import chat as chat_service
from rag import llm as llm_service
from rag import services, vector_store
from rag.models import Chunk, Document, KnowledgeBase, Message, Session
from rag.serializers import (
    ChatRequestSerializer,
    ChunkSerializer,
    DocumentSerializer,
    KnowledgeBaseSerializer,
    MessageSerializer,
    SearchSerializer,
    SessionSerializer,
)

logger = logging.getLogger(__name__)


class KnowledgeBaseViewSet(viewsets.ModelViewSet):
    """知识库（共享同一检索索引的文档集合）。"""

    queryset = KnowledgeBase.objects.all()
    serializer_class = KnowledgeBaseSerializer
    lookup_field = "pk"
    pagination_class = None

    @action(detail=True, methods=["post"])
    def search(self, request, pk=None):
        """多阶段检索：向量召回 + 重排 + 相关性门控。"""
        kb = self.get_object()
        ser = SearchSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        top_k = ser.validated_data.get("top_k", settings.RAG_DEFAULT_TOP_K)
        try:
            envelope = services.retrieve(kb, ser.validated_data["query"], top_k=top_k)
        except RuntimeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(envelope)

    @action(detail=True, methods=["post"])
    def chat(self, request, pk=None):
        """SSE 聊天：检索 + 相关性门控 + 流式 LLM 回答。"""
        kb = self.get_object()
        ser = ChatRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        top_k = ser.validated_data.get("top_k", settings.RAG_DEFAULT_TOP_K)
        query = ser.validated_data["query"]

        session_id = ser.validated_data.get("session_id")
        if session_id is not None:
            session = Session.objects.filter(pk=session_id, kb=kb).first()
            if session is None:
                return Response(
                    {"detail": f"会话 {session_id} 不存在于该知识库"},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            session = Session.objects.create(
                kb=kb, title=query[:30] or "新会话"
            )

        response = StreamingHttpResponse(
            chat_service.chat_stream(kb, query, session, top_k=top_k),
            content_type="text/event-stream; charset=utf-8",
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response

    @action(detail=True, methods=["post"])
    def answer(self, request, pk=None):
        """非流式回答（旧接口）：返回单个 JSON 响应体。"""
        kb = self.get_object()
        ser = SearchSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        top_k = ser.validated_data.get("top_k", settings.RAG_DEFAULT_TOP_K)
        query = ser.validated_data["query"]

        try:
            result = services.retrieve(kb, query, top_k=top_k)
        except RuntimeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        if result["refused"]:
            return Response(
                {
                    "query": query,
                    "answer": chat_service.REFUSED_ANSWER,
                    "refused": True,
                    "threshold": result["threshold"],
                    "best_score": result["best_score"],
                    "results": [],
                }
            )
        if not llm_service.is_configured():
            return Response(
                {"detail": "未配置模型服务（RAG_LLM_BASE_URL / RAG_LLM_API_KEY），请使用 /search 接口"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            answer, n = llm_service.generate_answer(query, result["results"])
        except RuntimeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(
            {
                "query": query,
                "answer": answer,
                "refused": False,
                "used_chunks": n,
                "results": result["results"],
            }
        )

    @action(detail=True, methods=["get"])
    def documents(self, request, pk=None):
        """列出属于某个知识库的文档。"""
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

    def perform_destroy(self, instance):
        kb_id = instance.id
        instance.delete()
        # 删除向量集合；Chunk 行会随外键级联删除。
        try:
            vector_store.get_backend().clear_kb(kb_id)
        except Exception:
            logger.exception("清理知识库 %s 的向量数据失败", kb_id)


class DocumentViewSet(viewsets.ModelViewSet):
    """文档：上传文件并入库（解析 + 切分 + 向量化）。"""

    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    pagination_class = None

    def get_queryset(self):
        queryset = Document.objects.all()
        kb = self.request.query_params.get("kb")
        if kb:
            queryset = queryset.filter(kb=kb)
        return queryset

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
            chunk_total = services.ingest_document(
                document, raw, file_obj.content_type, file_obj.name
            )
        except ValueError as exc:
            # 不支持/无法读取的格式 -> 返回 400 及可读的错误信息。
            return Response(
                {"detail": str(exc), "document": DocumentSerializer(document).data},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except RuntimeError as exc:
            return Response(
                {"detail": str(exc), "document": DocumentSerializer(document).data},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
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
        instance = self.get_object()
        kb = instance.kb
        # 向量数据必须与 Chunk 行一并删除。
        try:
            vector_store.get_backend().delete_document(kb, instance.id)
        except Exception:
            logger.exception("删除文档 %s 的向量数据失败", instance.id)
        instance.delete()
        return Response(
            {
                "message": "已删除文档",
                "deleted_documents": 1,
                "knowledge_base_id": kb.id,
            }
        )


class ChunkViewSet(viewsets.ReadOnlyModelViewSet):
    """已索引片段的只读视图（调试 / 审计用）。"""

    queryset = Chunk.objects.select_related("document").all()
    serializer_class = ChunkSerializer
    pagination_class = None

    def get_queryset(self):
        queryset = Chunk.objects.select_related("document").all()
        kb = self.request.query_params.get("kb")
        document = self.request.query_params.get("document")
        if kb:
            queryset = queryset.filter(kb=kb)
        if document:
            queryset = queryset.filter(document=document)
        return queryset


class SessionViewSet(viewsets.ModelViewSet):
    """聊天会话；消息通过嵌套的 ``messages`` action 提供。"""

    queryset = Session.objects.all()
    serializer_class = SessionSerializer
    pagination_class = None

    def get_queryset(self):
        queryset = Session.objects.all()
        kb = self.request.query_params.get("kb")
        if kb:
            queryset = queryset.filter(kb=kb)
        return queryset

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response({"message": "已删除会话"})

    @action(detail=True, methods=["get"])
    def messages(self, request, pk=None):
        session = self.get_object()
        messages = Message.objects.filter(session=session)
        ser = MessageSerializer(messages, many=True)
        return Response(
            {
                "session": SessionSerializer(session).data,
                "count": messages.count(),
                "messages": ser.data,
            }
        )
