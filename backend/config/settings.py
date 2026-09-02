"""
Django settings for the RAG backend.

Pure backend: document ingestion for RAG analysis + knowledge base
retrieval APIs, built on Django + Django REST Framework.
"""

import os
from pathlib import Path

# The environment exports ALL_PROXY=socks://… which httpx (used internally by
# llama_index / ollama for localhost calls) cannot parse and raises
# "Unknown scheme for proxy URL". Local RAG services talk to 127.0.0.1, so we
# drop the SOCKS proxy vars process-wide; remote LLM calls use an explicit
# proxy in rag/llm.py and are unaffected.
for _proxy_var in ("ALL_PROXY", "all_proxy"):
    os.environ.pop(_proxy_var, None)
os.environ.setdefault("NO_PROXY", "*")
os.environ.setdefault("no_proxy", "*")

# Build paths inside the project like this: BASE_DIR / "subdir".
BASE_DIR = Path(__file__).resolve().parent.parent

def _env(name, default=""):
    return os.environ.get(name, default)


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = _env(
    "DJANGO_SECRET_KEY",
    "django-insecure-ja%u^1wwt-+tme=y6bw9bi5j@lsi)1@ro4i_u*=z1!e8ci2g6=",
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = _env("DJANGO_DEBUG", "1") == "1"

ALLOWED_HOSTS = [
    h.strip()
    for h in _env("DJANGO_ALLOWED_HOSTS", "*").split(",")
    if h.strip()
]

# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "rag",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases
# Defaults to SQLite for zero-config runs; switch DATABASE_URL / engine
# to MySQL/managed DB by overriding the env vars below.
DATABASES = {
    "default": {
        "ENGINE": _env("DB_ENGINE", "django.db.backends.sqlite3"),
        "NAME": _env("DB_NAME", str(BASE_DIR / "db.sqlite3")),
        "USER": _env("DB_USER", ""),
        "PASSWORD": _env("DB_PASSWORD", ""),
        "HOST": _env("DB_HOST", ""),
        "PORT": _env("DB_PORT", ""),
    }
}

# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = "zh-hans"

TIME_ZONE = "Asia/Shanghai"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = _env("MEDIA_ROOT", str(BASE_DIR / "media"))

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ---- Django REST Framework ----
# Authentication classes are intentionally cleared: this deployment has no
# user system, and DRF's CSRF check only fires when SessionAuthentication
# finds an authenticated session. With the classes empty, session cookies
# (e.g. from an /admin login in the same browser) never trigger CSRF errors
# on the JSON/SSE endpoints.
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
}

# ---- CORS ----
CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = [
    o.strip()
    for o in _env("DJANGO_CORS_ALLOWED_ORIGINS", "").split(",")
    if o.strip()
]

# ---- RAG specific settings ----
# Maximum bytes accepted for a single uploaded document.
RAG_MAX_UPLOAD_BYTES = int(_env("RAG_MAX_UPLOAD_BYTES", "50_000_000"))
# Chunk size (in characters) used by the LlamaIndex sentence splitter.
RAG_CHUNK_SIZE = int(_env("RAG_CHUNK_SIZE", "500"))
# Overlap (in characters) between consecutive chunks.
RAG_CHUNK_OVERLAP = int(_env("RAG_CHUNK_OVERLAP", "50"))
# Default number of results returned by the retrieval API.
RAG_DEFAULT_TOP_K = int(_env("RAG_DEFAULT_TOP_K", "8"))

# ---- RAG / LlamaIndex embedding ----
# Ollama service hosting the local embedding + chat models (offline RAG).
RAG_OLLAMA_BASE_URL = _env("RAG_OLLAMA_BASE_URL", "http://127.0.0.1:11434")
# How long Ollama keeps embedding/generation models resident (ms or e.g. "30m", "-1" = forever).
RAG_OLLAMA_KEEP_ALIVE = _env("RAG_OLLAMA_KEEP_ALIVE", "30m")
# Embedding model used to build the vector index (bge-m3 is multilingual,
# good for Chinese). Use "lexical" to select a dependency-free fallback
# embedding that works without an Ollama server.
RAG_EMBEDDING_MODEL = _env("RAG_EMBEDDING_MODEL", "bge-m3")
RAG_EMBEDDING_PROVIDER = _env("RAG_EMBEDDING_PROVIDER", "ollama")
RAG_EMBEDDING_DIM = int(_env("RAG_EMBEDDING_DIM", "1024"))
# Directory where per-knowledge-base LlamaIndex stores are persisted.
RAG_INDEX_DIR = _env("RAG_INDEX_DIR", str(BASE_DIR / "rag_index"))

# ---- RAG / LLM (answer generation) ----
# "ollama" (local, default) or "openai" (OpenAI-compatible remote endpoint).
RAG_LLM_PROVIDER = _env("RAG_LLM_PROVIDER", "ollama")
RAG_LLM_MODEL = _env("RAG_LLM_MODEL", "qwen3:8b")
# OpenAI-compatible settings (only used when RAG_LLM_PROVIDER == "openai").
RAG_LLM_BASE_URL = _env("RAG_LLM_BASE_URL", "")
RAG_LLM_API_KEY = _env("RAG_LLM_API_KEY", "")
RAG_LLM_HTTP_PROXY = _env("RAG_LLM_HTTP_PROXY", "")
# Timeout (seconds) for a single LLM answer call.
RAG_LLM_TIMEOUT = int(_env("RAG_LLM_TIMEOUT", "300"))

# ---- RAG / vector store ----
# "milvus" (Milvus Lite embedded, default) or "memory" (LlamaIndex disk
# persistence; used by hermetic tests and as an explicit fallback).
RAG_VECTOR_BACKEND = _env("RAG_VECTOR_BACKEND", "milvus")
# Milvus Lite data location. May be a file or a directory (engine decides).
RAG_MILVUS_URI = _env("RAG_MILVUS_URI", str(BASE_DIR / "data" / "milvus" / "milvus.db"))
# When the Milvus backend fails to initialise, fall back to "memory" so the
# API stays usable (chunks in MySQL remain the source of truth).
RAG_VECTOR_FALLBACK_TO_MEMORY = _env("RAG_VECTOR_FALLBACK_TO_MEMORY", "1") == "1"
# How many texts per batch when embedding document chunks.
RAG_EMBED_BATCH_SIZE = int(_env("RAG_EMBED_BATCH_SIZE", "32"))

# ---- RAG / reranker ----
# "fusion" (local, zero-dependency hybrid of vector score + BM25-like lexical
# score) or "api" (OpenAI-compatible /rerank endpoint; reserved for later).
RAG_RERANK_PROVIDER = _env("RAG_RERANK_PROVIDER", "fusion")
# Weight of the vector score in the fused score (1-alpha for lexical).
RAG_RERANK_ALPHA = float(_env("RAG_RERANK_ALPHA", "0.6"))
# First stage recall = top_k * RAG_RECALL_MULTIPLIER, capped at RAG_RECALL_MAX.
RAG_RECALL_MULTIPLIER = int(_env("RAG_RECALL_MULTIPLIER", "3"))
RAG_RECALL_MAX = int(_env("RAG_RECALL_MAX", "50"))

# ---- RAG / anti-hallucination ----
# Below this best (reranked) relevance score the system refuses to answer
# without an LLM call ("根据现有知识库无法回答"). Tune for the embedding
# model in use; the lexical fallback embedding produces much lower scores.
# bge-m3 note: unrelated Chinese queries typically score 0.30-0.45 cosine,
# so the default sits at 0.40; calibrate with a few unrelated probe queries.
RAG_SIMILARITY_THRESHOLD = float(_env("RAG_SIMILARITY_THRESHOLD", "0.40"))

# ---- RAG / chat history ----
# Number of previous user/assistant turns (per session) injected into the
# LLM prompt as conversation context.
RAG_CHAT_HISTORY_TURNS = int(_env("RAG_CHAT_HISTORY_TURNS", "4"))
