from rest_framework import serializers

from rag.models import Chunk, Document, KnowledgeBase, Message, Session


class KnowledgeBaseSerializer(serializers.ModelSerializer):
    document_count = serializers.IntegerField(read_only=True)
    chunk_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = KnowledgeBase
        fields = [
            "id",
            "name",
            "description",
            "document_count",
            "chunk_count",
            "created_at",
        ]
        read_only_fields = ["id", "document_count", "chunk_count", "created_at"]

    def validate_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("名称不能为空")
        return value.strip()


class DocumentSerializer(serializers.ModelSerializer):
    knowledge_base = serializers.CharField(
        source="kb.name", read_only=True
    )
    chunk_count = serializers.IntegerField(
        source="chunks.count", read_only=True
    )

    class Meta:
        model = Document
        fields = [
            "id",
            "kb",
            "knowledge_base",
            "title",
            "file_name",
            "content_type",
            "size",
            "status",
            "error",
            "chunk_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "status", "error", "created_at", "updated_at"]


class ChunkSerializer(serializers.ModelSerializer):
    document_title = serializers.CharField(source="document.title", read_only=True)

    class Meta:
        model = Chunk
        fields = [
            "id",
            "kb",
            "document",
            "document_title",
            "index",
            "page",
            "text",
        ]


class SessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Session
        fields = ["id", "kb", "title", "created_at"]
        read_only_fields = ["id", "created_at"]


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = [
            "id",
            "session",
            "role",
            "content",
            "sources",
            "created_at",
        ]
        read_only_fields = ["id", "session", "created_at"]


class SearchSerializer(serializers.Serializer):
    query = serializers.CharField(
        max_length=2000, allow_blank=False, trim_whitespace=True
    )
    top_k = serializers.IntegerField(min_value=1, max_value=100, required=False)

    def validate_query(self, value):
        if not value.strip():
            raise serializers.ValidationError("查询内容不能为空")
        return value


class ChatRequestSerializer(serializers.Serializer):
    query = serializers.CharField(
        max_length=2000, allow_blank=False, trim_whitespace=True
    )
    session_id = serializers.IntegerField(min_value=1, required=False)
    top_k = serializers.IntegerField(min_value=1, max_value=100, required=False)

    def validate_query(self, value):
        if not value.strip():
            raise serializers.ValidationError("查询内容不能为空")
        return value


class RetrieveResultSerializer(serializers.Serializer):
    score = serializers.FloatField()
    rerank_score = serializers.FloatField()
    chunk_id = serializers.IntegerField()
    document_id = serializers.IntegerField()
    document_title = serializers.CharField()
    chunk_index = serializers.IntegerField()
    page = serializers.IntegerField(allow_null=True)
    text = serializers.CharField()
