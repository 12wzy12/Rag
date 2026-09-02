from django.urls import include, path
from rest_framework.routers import DefaultRouter

from rag.views import ChunkViewSet, DocumentViewSet, KnowledgeBaseViewSet

router = DefaultRouter()
router.register(
    "knowledge-bases", KnowledgeBaseViewSet, basename="knowledge-base"
)
router.register("documents", DocumentViewSet, basename="document")
router.register("chunks", ChunkViewSet, basename="chunk")

app_name = "rag"

urlpatterns = [
    path("", include(router.urls)),
]
