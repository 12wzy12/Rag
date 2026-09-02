from django.contrib import admin

from rag.models import Chunk, Document, KnowledgeBase


@admin.register(KnowledgeBase)
class KnowledgeBaseAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "created_at")
    search_fields = ("name", "description")


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "kb", "title", "status", "size", "created_at")
    list_filter = ("status", "kb")
    search_fields = ("title", "file_name")


@admin.register(Chunk)
class ChunkAdmin(admin.ModelAdmin):
    list_display = ("id", "kb", "document", "index")
    list_filter = ("kb",)
    search_fields = ("text",)
