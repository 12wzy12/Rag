from django.db import models
from django.utils import timezone


class KnowledgeBase(models.Model):
    """共享同一检索索引的文档的逻辑集合。"""

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
    # 文档解析后提取出的完整纯文本。
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
    """文档的一个索引片段，在文档入库时生成。"""

    kb = models.ForeignKey(
        KnowledgeBase, related_name="chunks", on_delete=models.CASCADE
    )
    document = models.ForeignKey(
        Document, related_name="chunks", on_delete=models.CASCADE
    )
    index = models.PositiveIntegerField()
    text = models.TextField()
    # 分页格式（如 PDF）的来源页码；其他格式为 None。
    page = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["document", "index"]
        indexes = [models.Index(fields=["kb"])]

    def __str__(self):
        return f"{self.document_id}:{self.index}"


class Session(models.Model):
    """绑定到某个知识库的聊天会话（保存对话历史）。"""

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
    """聊天会话中的一轮消息；助手轮次会保留其引用来源。"""

    class Role(models.TextChoices):
        USER = "user", "用户"
        ASSISTANT = "assistant", "助手"

    session = models.ForeignKey(
        Session, related_name="messages", on_delete=models.CASCADE
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    content = models.TextField()
    # 支撑助手回答的检索片段（JSON 列表，元素含
    # {score, rerank_score, chunk_id, document_id, document_title,
    #  chunk_index, page, text}）；用户轮次与拒绝回答时为空列表。
    sources = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["id"]
        indexes = [models.Index(fields=["session"])]

    def __str__(self):
        return f"{self.session_id}:{self.role}"
