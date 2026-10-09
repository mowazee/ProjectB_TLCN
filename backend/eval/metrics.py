"""Chỉ số đánh giá NFR-08: CER, WER, độ chính xác ký tự = 1 - CER (D-06). Không phụ thuộc thư viện ngoài.

Chuẩn hóa trước khi so: Unicode NFC, gộp khoảng trắng, bỏ khoảng trắng đầu/cuối. Giữ dấu và hoa/thường
(lỗi mất dấu tiếng Việt PHẢI bị tính là lỗi).
"""

import unicodedata
from collections.abc import Sequence


def normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).split())


def levenshtein(a: Sequence[object], b: Sequence[object]) -> int:
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def cer(reference: str, hypothesis: str) -> float:
    ref, hyp = normalize(reference), normalize(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0
    return levenshtein(ref, hyp) / len(ref)


def wer(reference: str, hypothesis: str) -> float:
    ref, hyp = normalize(reference).split(), normalize(hypothesis).split()
    if not ref:
        return 0.0 if not hyp else 1.0
    return levenshtein(ref, hyp) / len(ref)


def char_accuracy(reference: str, hypothesis: str) -> float:
    """Độ chính xác ký tự theo D-06 (có thể âm nếu chèn quá nhiều; báo cáo cắt về 0)."""
    return max(0.0, 1.0 - cer(reference, hypothesis))


def corpus_cer(pairs: list[tuple[str, str]]) -> float:
    """CER gộp theo tổng ký tự (không phải trung bình từng mẫu) - dùng cho con số báo cáo."""
    errors = sum(levenshtein(normalize(r), normalize(h)) for r, h in pairs)
    total = sum(len(normalize(r)) for r, _ in pairs)
    return errors / total if total else 0.0


def corpus_wer(pairs: list[tuple[str, str]]) -> float:
    errors = sum(levenshtein(normalize(r).split(), normalize(h).split()) for r, h in pairs)
    total = sum(len(normalize(r).split()) for r, _ in pairs)
    return errors / total if total else 0.0
