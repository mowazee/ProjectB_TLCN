"""Tính khung highlight từ khóa trên ảnh trang từ ocr_results.boxes (P2-02). Python thuần (R3).

boxes là danh sách dòng {text, score, box:[x,y,w,h]} theo pixel ảnh trang. Mỗi lần xuất hiện của
từ khóa (không phân biệt dấu/hoa thường, khoảng trắng linh hoạt) trong một dòng được đổi thành khung
con theo tỉ lệ ký tự trong dòng. fold() giữ nguyên độ dài nên vị trí trên text đã fold = vị trí gốc.
Khớp vắt qua hai dòng không được đánh dấu (giới hạn đã biết, đo trên tập mẫu).
"""

import re
from dataclasses import dataclass
from typing import Any

from app.modules.search.domain.normalize import fold, nfc, normalize_query

# Lý do trả danh sách rỗng (SDD 7.2: "rỗng kèm lý do khi không ánh xạ được")
EMPTY_QUERY = "empty_query"
NO_OCR = "no_ocr"
NO_BOXES = "no_boxes"
TEXT_MODIFIED = "text_modified"
NOT_FOUND = "not_found"


@dataclass(frozen=True)
class HighlightBox:
    x: int
    y: int
    w: int
    h: int
    line: int  # chỉ số dòng trong boxes
    start: int  # vị trí ký tự trong dòng
    end: int


def query_pattern(q: str) -> re.Pattern[str] | None:
    words = normalize_query(q).split()
    if not words:
        return None
    return re.compile(r"\s+".join(re.escape(w) for w in words))


def lines_text(boxes: list[dict[str, Any]]) -> str:
    """Text tái dựng từ boxes theo đúng cách OCR ghép raw_text (bỏ dòng rỗng)."""
    return "\n".join(str(b.get("text", "")) for b in boxes if str(b.get("text", "")).strip())


def compute(
    q: str, boxes: list[dict[str, Any]], *, effective_text: str, raw_text: str
) -> tuple[list[HighlightBox], str | None]:
    pattern = query_pattern(q)
    if pattern is None:
        return [], EMPTY_QUERY
    usable = [b for b in boxes if isinstance(b.get("box"), list | tuple) and len(b["box"]) == 4]
    if not usable or not any(int(b["box"][2]) > 0 and int(b["box"][3]) > 0 for b in usable):
        return [], NO_BOXES
    # Trang đã sửa làm lệch ánh xạ text-box: không vẽ sai, bỏ highlight và báo rõ
    if effective_text.strip() != raw_text.strip() or lines_text(boxes).strip() != raw_text.strip():
        return [], TEXT_MODIFIED
    out: list[HighlightBox] = []
    for i, b in enumerate(boxes):
        text = str(b.get("text", ""))
        box = b.get("box")
        if not text or not isinstance(box, list | tuple) or len(box) != 4:
            continue
        x, y, w, h = (int(v) for v in box)
        if w <= 0 or h <= 0:
            continue
        folded = fold(nfc(text))
        n = len(folded)
        for m in pattern.finditer(folded):
            x0 = x + round(w * m.start() / n)
            x1 = x + round(w * m.end() / n)
            out.append(HighlightBox(x0, y, max(1, x1 - x0), h, i, m.start(), m.end()))
    return out, (None if out else NOT_FOUND)
