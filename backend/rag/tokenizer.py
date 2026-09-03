"""轻量级、支持中日韩文字的分词器。

没有外部 NLP 依赖（离线环境无 jieba/torch），因此使用确定性的
词法分词方案：

- 连续的 CJK 字符（中/日文全角文字）-> 生成重叠的字符二元组，
  无需分词模型即可覆盖大部分常见的中文二字词。
- 连续的 ASCII 字母/数字 -> 转为小写词条。
"""

import re

_CJK_RUN = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]+")
_WORD_RUN = re.compile(r"[a-zA-Z0-9]+")
_SCAN = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]+|[a-zA-Z0-9]+")


def _cjk_tokens(run):
    if len(run) == 1:
        return [run]
    # 生成重叠二元组："机器学习" -> 机器, 器学, 学习
    return [run[i : i + 2] for i in range(len(run) - 1)]


def tokenize(text):
    """返回原始词条列表（可能包含重复项）。"""
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
    """返回一段文本的词条集合（去重后）。"""
    return set(tokenize(text))
