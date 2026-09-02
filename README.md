# RAG 智能知识库问答系统

基于 **Vue3 + Django REST Framework + LlamaIndex + Milvus** 的企业级 RAG 智能知识库问答系统：多格式文档上传解析、知识库构建、多阶段语义检索（向量召回 → 融合重排）、相似度阈值防幻觉、带来源引用的 SSE 流式智能问答。

```
                         ┌──────────────────────────────────────────────┐
                         │                  前端 (Vue3)                 │
                         │  知识库管理 · 文档上传 · 语义检索 · 流式对话  │
                         └───────────────┬──────────────────────────────┘
                                         │ REST / SSE (EventSource over fetch)
                         ┌───────────────▼──────────────────────────────┐
                         │          Django REST Framework               │
                         │  /search   /chat(SSE)  /sessions   CRUD      │
                         └───────┬───────────────────────┬──────────────┘
                                 │                       │
         业务数据 (MySQL/SQLite)  │                       │  向量数据 (Milvus Lite)
   ┌─────────────────────────────▼──────┐     ┌──────────▼──────────────────────┐
   │ KnowledgeBase / Document / Session │     │ kb_{id}_v1024 集合（每知识库一个）│
   │ / Message / Chunk(含 page 元数据)   │     │ HNSW / COSINE · 按 document 过滤 │
   └─────────────────────────────────────┘     └──────────┬──────────────────────┘
                                                          │
   RAG Pipeline（后端 rag/ 服务层）────────────────────────┘
   文档解析(PDF按页/DOCX/文本) → 文本清洗 → SentenceSplitter 切分(page 元数据)
   → BGE-M3 Embedding(Ollama) → Milvus 向量写入 → 检索: 向量召回 top_k×3
   → Fusion Reranker(BM25 词法分+向量分) → 相关性阈值判定(拒答) → Prompt 构建
   → LLM(qwen3/Ollama 或 OpenAI 兼容) SSE 流式生成 → 回答持久化+来源引用
```

## 技术栈与亮点

| 模块 | 实现 |
|---|---|
| 前后端分离 | Vue3 + Pinia + Vue Router + Vite；Django + DRF；开发期 Vite 代理 `/api` |
| RAG 管线 | 文档解析 → 清洗 → 切分 → Embedding → Milvus → Retriever → Reranker → Prompt → LLM（LlamaIndex SentenceSplitter 切分 + OllamaEmbedding） |
| 多格式解析 | PDF（PyMuPDF 按页提取，保留页码）、Word(docx)、Markdown/TXT/CSV/JSON/HTML/XML |
| 向量存储 | Milvus Lite（嵌入式，API 与 Milvus Standalone 一致）：每知识库一个 collection，HNSW/COSINE；Milvus 不可用时自动降级 LlamaIndex 磁盘索引 |
| 多阶段检索 | 一阶段向量召回 top_k×3（cap 50）→ 二阶段 Fusion Reranker：BM25 词法分（自研 CJK 分词）与向量分 min-max 归一化后按 α=0.6 融合 |
| 防幻觉 | 最高相关度低于 `RAG_SIMILARITY_THRESHOLD` 时**拒绝回答**（不调 LLM）；Prompt 约束仅依据检索片段 |
| 来源引用 | Document / Page / Chunk 三级元数据贯通，回答携带可展开的引用片段卡片 |
| 流式对话 | `POST /chat/` SSE：`sources → chunk* → done`；会话与消息（含来源 JSON）持久化，多轮历史注入 Prompt |
| 数据分层 | 知识库 → 文档 → 会话/消息；业务数据（MySQL/SQLite）与向量数据（Milvus）分离存储 |
| 部署 | Docker：nginx(前端+SSE 反代) + Django(gunicorn) + MySQL；向量库内嵌于后端 |

## 快速启动（本地开发，Windows/macOS/Linux）

### 0. 前置：模型服务（Ollama，可选但强烈推荐）

```bash
# 安装 Ollama（https://ollama.com）后拉取模型：
ollama pull bge-m3        # Embedding（多语言，中文效果好）
ollama pull qwen3:8b      # 生成模型（CPU 较弱可改用 qwen3:4b）
```

> 没有 Ollama 也能跑通**除 LLM 流式生成外的全部链路**：设置
> `RAG_EMBEDDING_PROVIDER=lexical`、`RAG_VECTOR_BACKEND=milvus`、
> `RAG_SIMILARITY_THRESHOLD=0.02`（lexical 分数偏低，需调低阈值）。

### 1. 后端

```bash
cd backend
python -m venv .venv && .venv\Scripts\activate        # Windows；macOS/Linux 用 .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env                                # 按需修改（默认 SQLite + Milvus Lite 零配置）
python manage.py migrate
python manage.py runserver 8000
```

### 2. 前端

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173，/api 自动代理到 :8000
```

浏览器打开 http://localhost:5173：新建知识库 → 上传 PDF/Word 文档 → 语义检索 → 流式问答（回答带来源卡片）。

### 3. 冒烟测试

```bash
cd backend && .venv\Scripts\activate

# 建库
curl -X POST http://127.0.0.1:8000/api/knowledge-bases/ -H "Content-Type: application/json" -d '{"name":"产品资料"}'

# 上传（PDF/Word/TXT/MD 均可，字段 file + kb）
curl -X POST http://127.0.0.1:8000/api/documents/ -F "file=@产品手册.pdf" -F "kb=1"

# 语义检索（多阶段：召回+重排+阈值判定）
curl -X POST http://127.0.0.1:8000/api/knowledge-bases/1/search/ \
  -H "Content-Type: application/json" -d '{"query":"定价规则是什么","top_k":8}'

# 流式问答（SSE，需 Ollama 已运行）
curl -N -X POST http://127.0.0.1:8000/api/knowledge-bases/1/chat/ \
  -H "Content-Type: application/json" -d '{"query":"定价规则是什么"}'
# 预期事件：event: sources → event: chunk(多次) → event: done
```

## Docker 部署

```bash
# 前置：宿主机运行 Ollama（Windows Docker Desktop 自动解析 host.docker.internal）
docker compose up -d --build
# 首次执行迁移：
docker compose exec backend python manage.py migrate
# 访问 http://localhost
```

- `docker-compose.yml`：mysql:8 + backend（内嵌 Milvus Lite，数据卷 `milvus-data`）+ frontend（nginx，SSE 反代已关 buffering）。
- 对接独立 Milvus Standalone：见 `docker-compose.yml` 内注释（`--profile milvus-standalone` + 改 `RAG_MILVUS_URI`）。

## API 概览（前缀 `/api`）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET/POST | `/knowledge-bases/` | 知识库列表 / 新建 |
| DELETE | `/knowledge-bases/{id}/` | 删除（级联文档/会话并清向量集合） |
| POST | `/knowledge-bases/{id}/search/` | 多阶段检索（返回 `refused/threshold/best_score/rerank_score/page`） |
| POST | `/knowledge-bases/{id}/chat/` | SSE 流式问答 `{query, session_id?, top_k?}` |
| GET/POST | `/documents/?kb=` `/documents/` | 文档列表（按库过滤）/ 上传（multipart `file`+`kb`，同步解析向量化） |
| DELETE | `/documents/{id}/` | 删除（同步清除向量） |
| GET | `/chunks/?kb=&document=` | 文本块（含 page 元数据，审计用） |
| GET/POST/DELETE | `/sessions/` `/sessions/{id}/` | 会话列表/新建/删除 |
| GET | `/sessions/{id}/messages/` | 会话消息（assistant 消息带 `sources`） |

### SSE 事件序列（`/chat/`）

```
sources  {session_id, count, refused, threshold, best_score, results:[...]}   # 检索+重排结果
chunk    {text}                        # 答案增量（多次）
done     {session_id, message_id}      # 正常结束
refused  {session_id, message, ...}    # 无足够依据拒答（不调 LLM），随后 done
error    {message}                     # 检索/模型异常，流结束
```

## 关键配置（backend/.env，完整见 `.env.example`）

| 变量 | 默认 | 说明 |
|---|---|---|
| `RAG_VECTOR_BACKEND` | `milvus` | `milvus`（Lite 内嵌）/ `memory`（LlamaIndex 磁盘） |
| `RAG_MILVUS_URI` | `data/milvus/milvus.db` | Milvus Lite 数据位置 |
| `RAG_EMBEDDING_PROVIDER` | `ollama` | `ollama`(bge-m3) / `lexical`（零依赖演示） |
| `RAG_EMBEDDING_MODEL` | `bge-m3` | Ollama Embedding 模型 |
| `RAG_LLM_PROVIDER` | `ollama` | `ollama` / `openai`（OpenAI 兼容，配 BASE_URL/API_KEY） |
| `RAG_LLM_MODEL` | `qwen3:8b` | 生成模型 |
| `RAG_RERANK_ALPHA` | `0.6` | 融合重排中向量分权重 |
| `RAG_SIMILARITY_THRESHOLD` | `0.40` | 拒答阈值（bge-m3 对无关中文 query 余弦常在 0.30~0.45，建议实测校准；lexical 嵌入需 ~0.02） |
| `RAG_CHUNK_SIZE/OVERLAP` | `500/50` | 切分参数 |
| `DB_ENGINE` | sqlite3 | 切 mysql 见 `.env.example` |

## 目录结构

```
backend/
  config/            # Django 配置（settings/urls）
  rag/
    parsers.py       # 文档解析（PDF 按页/DOCX/文本）→ [{page,text}]
    chunking.py      # LlamaIndex SentenceSplitter 切分（携带 page 元数据）
    vector_store.py  # Milvus(Lite) 后端 + memory 降级
    reranker.py      # Fusion 二阶段重排（BM25 + 向量分）
    services.py      # 摄取与检索管线（多阶段、统一信封）
    chat.py          # SSE 事件流（检索→阈值→流式生成→持久化）
    llm.py           # Ollama / OpenAI 兼容 LLM（流式+非流式）
    views.py         # REST 端点 + SSE chat
frontend/
  src/views/         # 知识库管理 / 文档 / 语义检索 / 智能问答
  src/components/    # kb / documents / search / chat / ui
  src/api/           # 对齐后端契约的 axios/fetch 封装（chat 为手写 SSE）
docker-compose.yml   # mysql + backend + frontend（+可选 Milvus profile）
```

## 已知限制

- 文档解析与向量化在请求内同步完成，超大 PDF 会阻塞该请求（本地工具定位足够；生产可演进为后台任务）。
- 换用不同维度/模型的 Embedding 时，Milvus 按 `dim` 自动新建集合，旧数据需重新上传（README 提示）；同维度换模型需手动删除 `data/milvus` 后重灌。
- Milvus Lite 单进程、本地单机定位；生产多副本请对接 Milvus Standalone（PyMilvus 访问层代码不变）。
