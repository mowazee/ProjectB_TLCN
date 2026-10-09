"""Quy tắc trích xuất trường (P2-04) bằng regex trên text hiệu lực. Python thuần (R3).

Khớp trên text đã fold (không dấu, chữ thường, cùng độ dài) rồi cắt giá trị từ text gốc nên vẫn giữ
dấu tiếng Việt và chịu được OCR mất dấu. Bộ trường chung cho văn bản hành chính (Nghị định
30/2020/NĐ-CP: số, ký hiệu; ngày ban hành; cơ quan ban hành; người ký; trích yếu) + bổ sung theo
mã danh mục (vd. HOP-DONG). precision/recall đo bằng eval/extraction_eval.py trên tập mẫu.
"""

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass

METHOD = "regex-v1"


def _fold(text: str) -> str:
    out = []
    for ch in unicodedata.normalize("NFC", text):
        if ch in "đĐ":
            out.append("d")
        elif ch.isspace():
            out.append("\n" if ch == "\n" else " ")  # giữ xuống dòng cho quy tắc theo dòng
        else:
            base = unicodedata.normalize("NFD", ch)[0].lower()
            out.append(base if len(base) == 1 else ch)
    return "".join(out)


@dataclass(frozen=True)
class FieldRule:
    name: str
    label: str
    patterns: tuple[str, ...]  # regex trên text đã fold, nhóm "v" là giá trị
    clean: Callable[[str], str] | None = None


@dataclass(frozen=True)
class Extracted:
    name: str
    value: str
    start: int


def _strip(v: str) -> str:
    return v.strip(" .,:;-\t")


def _date(v: str) -> str:
    """Chuẩn hóa ngày về YYYY-MM-DD khi đọc được; ngược lại giữ nguyên."""
    m = re.search(r"(\d{1,2})\D{1,10}?(\d{1,2})\D{1,10}?(\d{4})", v)
    if m:
        d, mo, y = (int(x) for x in m.groups())
        if 1 <= d <= 31 and 1 <= mo <= 12:
            return f"{y:04d}-{mo:02d}-{d:02d}"
    return _strip(v)


_COMMON: tuple[FieldRule, ...] = (
    FieldRule(
        "so_hieu",
        "Số, ký hiệu",
        (r"\bso\s*[:.]?\s*(?P<v>\d{1,6}\s*/\s*(?:\d{4}\s*/\s*)?[a-z0-9]+(?:\s*-\s*[a-z0-9]+)*)",),
        lambda v: re.sub(r"\s+", "", v).upper(),
    ),
    FieldRule(
        "ngay_ban_hanh",
        "Ngày ban hành",
        (
            r"\bngay\s+(?P<v>\d{1,2}\s+thang\s+\d{1,2}\s+nam\s+\d{4})",
            r"\bngay\s*(?P<v>\d{1,2}\s*[/.-]\s*\d{1,2}\s*[/.-]\s*\d{4})",
        ),
        _date,
    ),
    FieldRule(
        "co_quan_ban_hanh",
        "Cơ quan ban hành",
        (
            r"^\s*(?P<v>(?:uy ban nhan dan|bo|so|cong ty|tong cong ty|truong|ngan hang|tap doan|"
            r"chi cuc|cuc|vien|benh vien|hoi dong) +[a-z][^\n:0-9]{1,80})$",  # tên cơ quan: không ':' hay số
        ),
        _strip,
    ),
    FieldRule(
        "nguoi_ky",
        "Người ký",
        (
            r"\b(?:ky ten|nguoi ky|ky boi)\s*[:.]?\s*(?P<v>[^\n]{3,60})",
            r"(?:giam doc|chu tich|truong phong|hieu truong|thu truong|bo truong|tong giam doc)\s*\n+\s*"
            r"(?:\(ky[^)\n]*\)\s*\n+\s*)?(?P<v>[^\n\d]{3,50})\s*$",
        ),
        _strip,
    ),
    FieldRule(
        "trich_yeu",
        "Trích yếu",
        (r"\bv/v\s*[:.]?\s*(?P<v>[^\n]{5,200})", r"\bve viec\s*[:.]?\s*(?P<v>[^\n]{5,200})"),
        _strip,
    ),
)

_BY_CATEGORY: dict[str, tuple[FieldRule, ...]] = {
    "HOP-DONG": (
        FieldRule(
            "ben_a",
            "Bên A",
            (r"\bben a\b\s*(?:\([^)\n]*\))?\s*[:.]?\s*(?P<v>[^\n]{3,120})",),
            _strip,
        ),
        FieldRule(
            "ben_b",
            "Bên B",
            (r"\bben b\b\s*(?:\([^)\n]*\))?\s*[:.]?\s*(?P<v>[^\n]{3,120})",),
            _strip,
        ),
        FieldRule(
            "gia_tri",
            "Giá trị hợp đồng",
            (r"\bgia tri(?: hop dong)?\s*(?:la)?\s*[:.]?\s*(?P<v>[\d.,\s]{3,30}\s*(?:vnd|dong|d)\b)",),
            _strip,
        ),
    ),
}


def rules_for(category_code: str | None) -> tuple[FieldRule, ...]:
    return _COMMON + _BY_CATEGORY.get((category_code or "").upper(), ())


def field_labels(category_code: str | None) -> dict[str, str]:
    return {r.name: r.label for r in rules_for(category_code)}


def extract(text: str, category_code: str | None) -> list[Extracted]:
    original = unicodedata.normalize("NFC", text)
    folded = _fold(original)
    found: list[Extracted] = []
    for rule in rules_for(category_code):
        for pat in rule.patterns:
            m = re.search(pat, folded, flags=re.MULTILINE)
            if m:
                raw = original[m.start("v") : m.end("v")]
                value = rule.clean(raw) if rule.clean else raw.strip()
                if value:
                    found.append(Extracted(rule.name, value[:1000], m.start("v")))
                    break
    return found
