"""Second-stage reranking of first-stage vector recall.

Two providers:

- ``fusion`` (default): zero-dependency hybrid reranker. Each candidate gets a
  BM25-like lexical score against the query (built on the project's own
  CJK-aware tokenizer, no external NLP deps) and the fused score is a convex
  combination of the normalised vector score and the normalised lexical
  score. This re-orders candidates whose lexical overlap is stronger than
  raw vector distance and requires no extra model or network.
- ``api``: reserved extension point for an OpenAI-compatible ``/rerank``
  endpoint (e.g. SiliconFlow's bge-reranker-v2-m3); implemented but off by
  default (``RAG_RERANK_PROVIDER=api`` + base URL/API key).
"""

import math

from django.conf import settings

from rag.tokenizer import tokenize

_K1 = 1.5
_B = 0.75


def _lexical_scores(query, candidates):
    """BM25-like scores of every candidate against the query.

    ``candidates`` are the candidate texts; scores use the corpus of the
    candidates themselves for document frequency and average length.
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
    """Re-rank first-stage ``candidates`` and return the best ``top_k``.

    ``candidates``: ``[{chunk_id, score, text}]`` (``score`` = raw vector
    similarity, descending). Returns the same dicts plus ``rerank_score``
    (the fused relevance, 0-1), re-ordered by fused score descending.
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
    """Rerank through an OpenAI-compatible ``/rerank`` endpoint.

    Enabled when ``RAG_RERANK_PROVIDER=api``; returns candidates sorted by
    the model score. Raises ``RuntimeError`` when unconfigured or on failure.
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

    # Accept both {"results": [{"index", "relevance_score"}]} and
    # {"data": [{"index", "score"}]} response shapes.
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
    # Candidates absent from the rerank response keep their vector rank.
    ordered.sort(key=lambda c: c["rerank_score"], reverse=True)
    return ordered[: int(top_k)]
