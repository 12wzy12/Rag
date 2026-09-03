"""第二阶段重排：对第一阶段向量召回的结果进行重排。

两种提供方：

- ``fusion``（默认）：零依赖的混合重排器。每个候选获得一个相对查询的
  类 BM25 词法评分（基于项目自带、可识别中日韩文本的分词器构建，无外部
  NLP 依赖），融合分数为归一化向量分数与归一化词法分数的凸组合。它能将
  词法重叠度强于原始向量距离的候选重新排到前面，且无需额外模型或网络。
- ``api``：面向兼容 OpenAI 的 ``/rerank`` 接口（如 SiliconFlow 的
  bge-reranker-v2-m3）预留的扩展点；已实现但默认关闭
  （``RAG_RERANK_PROVIDER=api`` + base URL/API key）。
"""

import math

from django.conf import settings

from rag.tokenizer import tokenize

_K1 = 1.5
_B = 0.75


def _lexical_scores(query, candidates):
    """计算每个候选相对查询的类 BM25 分数。

    ``candidates`` 为候选文本；词频（document frequency）与平均长度
    基于候选文本自身构成的语料进行统计。
    """
    query_tokens = list(dict.fromkeys(tokenize(query)))
    if not query_tokens or not candidates:
        return [0.0] * len(candidates)

    corpus = [tokenize(text) for text in candidates]
    n = len(corpus)
    doc_freq = {}
    for tokens in corpus:
        for token in set(tokens):
            doc_freq[token] = doc_freq.get(token, 0) + 1
    avg_len = sum(len(t) for t in corpus) / n

    def idf(token):
        df = doc_freq.get(token, 0)
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    scores = []
    for tokens in corpus:
        length = len(tokens)
        counts = {}
        for token in tokens:
            counts[token] = counts.get(token, 0) + 1
        score = 0.0
        for token in query_tokens:
            tf = counts.get(token, 0)
            if not tf:
                continue
            denominator = tf + _K1 * (1 - _B + _B * length / avg_len)
            score += idf(token) * (_K1 * tf / denominator)
        scores.append(score)
    return scores


def _min_max_normalise(values):
    if not values:
        return []
    low, high = min(values), max(values)
    if high - low < 1e-12:
        return [0.5] * len(values)
    return [(v - low) / (high - low) for v in values]


def rerank(query, candidates, top_k):
    """对第一阶段的 ``candidates`` 进行重排，返回最优的 ``top_k`` 个。

    ``candidates``：``[{chunk_id, score, text}]``（``score`` 为原始向量
    相似度，降序）。返回原有字典并附加 ``rerank_score``（融合相关度，
    取值 0-1），按融合分数降序重新排列。
    """
    if not candidates:
        return []
    if top_k is None:
        top_k = settings.RAG_DEFAULT_TOP_K

    vector_scores = [c["score"] for c in candidates]
    lexical_scores = _lexical_scores(query, [c["text"] for c in candidates])

    vector_norm = _min_max_normalise(vector_scores)
    lexical_norm = _min_max_normalise(lexical_scores)
    alpha = settings.RAG_RERANK_ALPHA

    fused = []
    for candidate, v, l in zip(candidates, vector_norm, lexical_norm):
        merged = dict(candidate)
        merged["rerank_score"] = round(alpha * v + (1 - alpha) * l, 6)
        fused.append(merged)

    fused.sort(key=lambda c: c["rerank_score"], reverse=True)
    return fused[: int(top_k)]


def rerank_api(query, candidates, top_k):
    """通过兼容 OpenAI 的 ``/rerank`` 接口进行重排。

    当 ``RAG_RERANK_PROVIDER=api`` 时启用；返回按模型分数排序的候选。
    未配置或调用失败时抛出 ``RuntimeError``。
    """
    base = getattr(settings, "RAG_RERANK_API_BASE_URL", "")
    key = getattr(settings, "RAG_RERANK_API_KEY", "")
    model = getattr(settings, "RAG_RERANK_MODEL", "")
    if not (base and key and model):
        raise RuntimeError("未配置 RAG_RERANK_API_BASE_URL / RAG_RERANK_API_KEY / RAG_RERANK_MODEL")

    import json
    import urllib.error
    import urllib.request

    payload = {
        "model": model,
        "query": query,
        "documents": [c["text"] for c in candidates],
        "top_n": int(top_k),
    }
    req = urllib.request.Request(
        f"{base.rstrip('/')}/rerank",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Rerank 接口返回 {exc.code}: {body[:300]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"无法连接 Rerank 服务: {exc.reason}") from exc

    # 同时兼容两种响应结构：{"results": [{"index", "relevance_score"}]}
    # 与 {"data": [{"index", "score"}]}。
    raw = data.get("results") or data.get("data") or []
    ranking = {}
    for item in raw:
        idx = item.get("index")
        score = item.get("relevance_score", item.get("score"))
        if idx is not None and score is not None:
            ranking[int(idx)] = float(score)

    ordered = []
    for index, candidate in enumerate(candidates):
        if index in ranking:
            merged = dict(candidate)
            merged["rerank_score"] = round(ranking[index], 6)
            ordered.append(merged)
    # 未出现在重排响应中的候选，保持其原有向量排名。
    ordered.sort(key=lambda c: c["rerank_score"], reverse=True)
    return ordered[: int(top_k)]
