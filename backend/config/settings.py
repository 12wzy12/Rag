"""
RAG 后端项目的 Django 配置。

纯后端服务：面向 RAG 分析的文档入库 + 知识库检索 API，
基于 Django + Django REST Framework 构建。
"""

import os
from pathlib import Path

# 环境中导出了 ALL_PROXY=socks://…，而 httpx（llama_index / ollama 访问
# localhost 时在内部使用）无法解析这种代理，会抛出 "Unknown scheme for
# proxy URL"。本地 RAG 服务均访问 127.0.0.1，因此在进程范围内移除 SOCKS
# 代理变量；远程 LLM 调用使用 rag/llm.py 中的显式代理，不受影响。
for _proxy_var in ("ALL_PROXY", "all_proxy"):
    os.environ.pop(_proxy_var, None)
os.environ.setdefault("NO_PROXY", "*")
os.environ.setdefault("no_proxy", "*")

# 项目内路径按 BASE_DIR / "子目录" 的方式构建。
BASE_DIR = Path(__file__).resolve().parent.parent

def _env(name, default=""):
    return os.environ.get(name, default)


# 安全警告：生产环境中请务必对 secret key 保密！
SECRET_KEY = _env(
    "DJANGO_SECRET_KEY",
    "django-insecure-ja%u^1wwt-+tme=y6bw9bi5j@lsi)1@ro4i_u*=z1!e8ci2g6=",
)

# 安全警告：生产环境中切勿开启 debug 运行！
DEBUG = _env("DJANGO_DEBUG", "1") == "1"

ALLOWED_HOSTS = [
    h.strip()
    for h in _env("DJANGO_ALLOWED_HOSTS", "*").split(",")
    if h.strip()
]

# 应用定义

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


# 数据库
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases
# 默认使用 SQLite，实现零配置运行；如需切换到 MySQL/托管数据库，
# 通过覆盖下方的环境变量修改 DATABASE_URL / engine。
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

# 密码校验
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


# 国际化
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = "zh-hans"

TIME_ZONE = "Asia/Shanghai"

USE_I18N = True

USE_TZ = True


# 静态文件（CSS、JavaScript、图片）
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = _env("MEDIA_ROOT", str(BASE_DIR / "media"))

# 默认主键字段类型
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ---- Django REST Framework ----
# 认证类被有意清空：本部署没有用户体系，且 DRF 的 CSRF 检查只在
# SessionAuthentication 检测到已认证会话时才会触发。认证类为空时，
# 会话 cookie（如同一浏览器中 /admin 登录产生的）不会在 JSON/SSE
# 接口上引发 CSRF 错误。
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

# ---- CORS（跨域资源共享） ----
CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = [
    o.strip()
    for o in _env("DJANGO_CORS_ALLOWED_ORIGINS", "").split(",")
    if o.strip()
]

# ---- RAG 通用设置 ----
# 单个上传文档允许的最大字节数。
RAG_MAX_UPLOAD_BYTES = int(_env("RAG_MAX_UPLOAD_BYTES", "50_000_000"))
# LlamaIndex 句子切分器使用的分块大小（按字符计）。
RAG_CHUNK_SIZE = int(_env("RAG_CHUNK_SIZE", "500"))
# 相邻分块之间的重叠长度（按字符计）。
RAG_CHUNK_OVERLAP = int(_env("RAG_CHUNK_OVERLAP", "50"))
# 检索 API 默认返回的结果数量。
RAG_DEFAULT_TOP_K = int(_env("RAG_DEFAULT_TOP_K", "8"))

# ---- RAG / LlamaIndex embedding ----
# 承载本地 embedding 与聊天模型的 Ollama 服务（离线 RAG）。
RAG_OLLAMA_BASE_URL = _env("RAG_OLLAMA_BASE_URL", "http://127.0.0.1:11434")
# Ollama 让 embedding/生成模型驻留内存的时长（毫秒，或如 "30m"；"-1" 表示永驻）。
RAG_OLLAMA_KEEP_ALIVE = _env("RAG_OLLAMA_KEEP_ALIVE", "30m")
# 用于构建向量索引的 embedding 模型（bge-m3 支持多语言，对中文效果良好）。
# 设为 "lexical" 可选择无需 Ollama 服务器、零依赖的回退 embedding。
RAG_EMBEDDING_MODEL = _env("RAG_EMBEDDING_MODEL", "bge-m3")
RAG_EMBEDDING_PROVIDER = _env("RAG_EMBEDDING_PROVIDER", "ollama")
RAG_EMBEDDING_DIM = int(_env("RAG_EMBEDDING_DIM", "1024"))
# 各知识库 LlamaIndex 存储的持久化目录。
RAG_INDEX_DIR = _env("RAG_INDEX_DIR", str(BASE_DIR / "rag_index"))

# ---- RAG / LLM（回答生成） ----
# "ollama"（本地，默认）或 "openai"（OpenAI 兼容的远程接口）。
RAG_LLM_PROVIDER = _env("RAG_LLM_PROVIDER", "ollama")
RAG_LLM_MODEL = _env("RAG_LLM_MODEL", "qwen3:8b")
# OpenAI 兼容相关设置（仅当 RAG_LLM_PROVIDER == "openai" 时使用）。
RAG_LLM_BASE_URL = _env("RAG_LLM_BASE_URL", "")
RAG_LLM_API_KEY = _env("RAG_LLM_API_KEY", "")
RAG_LLM_HTTP_PROXY = _env("RAG_LLM_HTTP_PROXY", "")
# 单次 LLM 回答调用的超时时间（秒）。
RAG_LLM_TIMEOUT = int(_env("RAG_LLM_TIMEOUT", "300"))

# ---- RAG / vector store ----
# "milvus"（内嵌 Milvus Lite，默认）或 "memory"（LlamaIndex 磁盘
# 持久化；供封闭式测试使用，也可作为显式回退方案）。
RAG_VECTOR_BACKEND = _env("RAG_VECTOR_BACKEND", "milvus")
# Milvus Lite 数据位置，可为文件或目录（由引擎自行决定）。
RAG_MILVUS_URI = _env("RAG_MILVUS_URI", str(BASE_DIR / "data" / "milvus" / "milvus.db"))
# 当 Milvus 后端初始化失败时回退到 "memory"，保证 API 依然可用
# （MySQL 中的 Chunk 数据始终是真正的数据源）。
RAG_VECTOR_FALLBACK_TO_MEMORY = _env("RAG_VECTOR_FALLBACK_TO_MEMORY", "1") == "1"
# 对文档分块做 embedding 时每批处理的文本条数。
RAG_EMBED_BATCH_SIZE = int(_env("RAG_EMBED_BATCH_SIZE", "32"))

# ---- RAG / reranker（重排器） ----
# "fusion"（本地、零依赖：向量得分 + BM25 式词法得分的混合）或 "api"
# （OpenAI 兼容的 /rerank 接口；预留待用）。
RAG_RERANK_PROVIDER = _env("RAG_RERANK_PROVIDER", "fusion")
# 融合得分中向量得分的权重（词法部分为 1-alpha）。
RAG_RERANK_ALPHA = float(_env("RAG_RERANK_ALPHA", "0.6"))
# 第一阶段的召回数量 = top_k * RAG_RECALL_MULTIPLIER，上限为 RAG_RECALL_MAX。
RAG_RECALL_MULTIPLIER = int(_env("RAG_RECALL_MULTIPLIER", "3"))
RAG_RECALL_MAX = int(_env("RAG_RECALL_MAX", "50"))

# ---- RAG / anti-hallucination（防幻觉） ----
# 最佳（重排后）相关度得分低于该阈值时，系统不调用 LLM 直接拒绝回答
# （"根据现有知识库无法回答"）。请针对所用 embedding 模型调优；
# lexical 回退 embedding 产生的得分会低很多。
# bge-m3 说明：无关的中文查询余弦得分通常在 0.30-0.45，
# 因此默认值取 0.40；可用若干无关的探测查询进行校准。
RAG_SIMILARITY_THRESHOLD = float(_env("RAG_SIMILARITY_THRESHOLD", "0.40"))

# ---- RAG / 对话历史 ----
# 作为对话上下文注入 LLM 提示词的（每会话）前几轮用户/助手消息数量。
RAG_CHAT_HISTORY_TURNS = int(_env("RAG_CHAT_HISTORY_TURNS", "4"))
