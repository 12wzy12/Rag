from django.db import models
from django.utils import timezone


class KnowledgeBase(models.Model):
    """A logical collection of documents that share one retrieval index."""

    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    @property
    def document_count(self):
        return self.documents.count()

    @property
    def chunk_count(self):
        return self.chunks.count()


class Document(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "待解析"
        PARSING = "parsing", "解析中"
        READY = "ready", "已就绪"
        FAILED = "failed", "解析失败"

    kb = models.ForeignKey(
        KnowledgeBase, related_name="documents", on_delete=models.CASCADE
    )
    title = models.CharField(max_length=500)
    file_name = models.CharField(max_length=500, blank=True, default="")
    content_type = models.CharField(max_length=200, blank=True, default="")
    size = models.PositiveBigIntegerField(default=0)
    # Full extracted plain-text of the document.
    text = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["kb", "status"])]

    def __str__(self):
        return f"{self.kb.name} / {self.title}"


class Chunk(models.Model):
    """One indexed segment of a document, produced at ingestion time."""

    kb = models.ForeignKey(
        KnowledgeBase, related_name="chunks", on_delete=models.CASCADE
    )
    document = models.ForeignKey(
        Document, related_name="chunks", on_delete=models.CASCADE
    )
    index = models.PositiveIntegerField()
    text = models.TextField()

    class Meta:
        ordering = ["document", "index"]
        indexes = [models.Index(fields=["kb"])]

    def __str__(self):
        return f"{self.document_id}:{self.index}"
