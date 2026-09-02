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
    # Source page number for paginated formats (PDF); None otherwise.
    page = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["document", "index"]
        indexes = [models.Index(fields=["kb"])]

    def __str__(self):
        return f"{self.document_id}:{self.index}"


class Session(models.Model):
    """A chat session bound to one knowledge base (conversation history)."""

    kb = models.ForeignKey(
        KnowledgeBase, related_name="sessions", on_delete=models.CASCADE
    )
    title = models.CharField(max_length=300)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.kb.name} / {self.title}"


class Message(models.Model):
    """One turn inside a chat session; assistant turns keep their sources."""

    class Role(models.TextChoices):
        USER = "user", "用户"
        ASSISTANT = "assistant", "助手"

    session = models.ForeignKey(
        Session, related_name="messages", on_delete=models.CASCADE
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    content = models.TextField()
    # Retrieval chunks backing an assistant answer (JSON list of
    # {score, rerank_score, chunk_id, document_id, document_title,
    #  chunk_index, page, text}); empty for user turns and refused answers.
    sources = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["id"]
        indexes = [models.Index(fields=["session"])]

    def __str__(self):
        return f"{self.session_id}:{self.role}"
