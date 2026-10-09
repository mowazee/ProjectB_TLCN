"""Chuẩn hóa văn bản cho phân loại (P2-05), Python thuần (R3).

OCR PaddleOCR `vi` hay mất dấu → bỏ dấu cả mẫu huấn luyện lẫn tài liệu cần phân loại để hai phía khớp nhau.
Đặc trưng: từ (đã bỏ dấu, bỏ stopword, dài > 1) + bigram nối bằng "_".
"""

import re
import unicodedata

_WORD = re.compile(r"[a-z0-9]+")
_STOP = frozenset(
    [
        "va",
        "cua",
        "cac",
        "la",
        "co",
        "cho",
        "nhung",
        "duoc",
        "trong",
        "voi",
        "mot",
        "nay",
        "theo",
        "tai",
        "ve",
        "tu",
        "den",
        "khi",
        "da",
        "se",
        "thi",
        "ma",
        "nhu",
        "boi",
        "tren",
    ]
)


def fold(text: str) -> str:
    s = unicodedata.normalize("NFD", text.replace("đ", "d").replace("Đ", "D"))
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn").lower()


def tokenize(text: str) -> list[str]:
    words = [w for w in _WORD.findall(fold(text)) if len(w) > 1 and w not in _STOP]
    return words + [f"{a}_{b}" for a, b in zip(words, words[1:], strict=False)]
