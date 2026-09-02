"""Lightweight CJK-aware tokenizer.

No external NLP dependencies (jieba/torch are not available offline), so we
use a deterministic lexical tokenizer:

- Runs of CJK characters (Chinese/Japanese full-width) -> overlapping
  character bigrams. This recovers most common 2-character Chinese words
  without a segmentation model.
- Runs of ASCII letters/digits -> lowercased word tokens.
"""

import re

_CJK_RUN = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]+")
_WORD_RUN = re.compile(r"[a-zA-Z0-9]+")
_SCAN = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]+|[a-zA-Z0-9]+")


def _cjk_tokens(run):
    if len(run) == 1:
        return [run]
    # Overlapping bigrams: "机器学习" -> 机器, 器学, 学习
    return [run[i : i + 2] for i in range(len(run) - 1)]


def tokenize(text):
    """Return a list of raw tokens (may contain duplicates)."""
    if not text:
        return []
    tokens = []
    for m in _SCAN.finditer(text):
        s = m.group()
        if _CJK_RUN.fullmatch(s):
            tokens.extend(_cjk_tokens(s))
        else:
            tokens.append(s.lower())
    return tokens


def unique_tokens(text):
    """Return the set of tokens for a piece of text."""
    return set(tokenize(text))
