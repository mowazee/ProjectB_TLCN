"""Chuẩn hóa text tiếng Việt cho chỉ mục (SDD mục 6: keyword chuẩn hóa).

Chữ thường, bỏ dấu, đ -> d, khoảng trắng -> " ", GIỮ NGUYÊN ĐỘ DÀI để ánh xạ vị trí khớp về
text gốc khi cắt snippet và khi tìm box (P2-02). Tìm không dấu còn bù lỗi mất dấu của OCR.
"""

import unicodedata
from functools import lru_cache


@lru_cache(maxsize=8192)
def _fold_char(ch: str) -> str:
    if ch in "đĐ":
        return "d"
    if ch.isspace():
        return " "
    base = unicodedata.normalize("NFD", ch)[0]
    low = base.lower()
    return low if len(low) == 1 else base


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def fold(text: str) -> str:
    """Đầu vào phải ở dạng NFC; đầu ra cùng độ dài."""
    return "".join(_fold_char(c) for c in text)


def normalize_query(q: str) -> str:
    return " ".join(fold(nfc(q)).split())
