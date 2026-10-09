"""Precision/recall trích xuất trường (P2-04) trên tập mẫu có đánh dấu.

    python eval/extraction_eval.py eval/data/extraction.jsonl

Mỗi dòng JSONL: {"text": "...", "category_code": "CONG-VAN", "fields": {"so_hieu": "123/2026/QĐ-UBND", ...}}
Một trường đúng khi giá trị trích xuất trùng giá trị đánh dấu sau chuẩn hóa (NFC, gộp khoảng trắng, chữ thường).
"""

import json
import sys
import unicodedata
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.modules.extraction.domain.rules import extract  # noqa: E402


def _n(v: str) -> str:
    return " ".join(unicodedata.normalize("NFC", v).lower().split())


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    tp: Counter[str] = Counter()
    fp: Counter[str] = Counter()
    fn: Counter[str] = Counter()
    for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        gold = {k: _n(v) for k, v in row["fields"].items() if v}
        pred = {e.name: _n(e.value) for e in extract(row["text"], row.get("category_code"))}
        for name in set(gold) | set(pred):
            if name in pred and name in gold and pred[name] == gold[name]:
                tp[name] += 1
            else:
                if name in pred:
                    fp[name] += 1
                if name in gold:
                    fn[name] += 1
    print(f"{'trường':<20}{'precision':>11}{'recall':>9}{'n':>5}")
    for name in sorted(set(tp) | set(fp) | set(fn)):
        p = tp[name] / (tp[name] + fp[name]) if tp[name] + fp[name] else 0.0
        r = tp[name] / (tp[name] + fn[name]) if tp[name] + fn[name] else 0.0
        print(f"{name:<20}{p:>11.2%}{r:>9.2%}{tp[name] + fn[name]:>5}")
    t, f_p, f_n = sum(tp.values()), sum(fp.values()), sum(fn.values())
    print(f"{'TỔNG (micro)':<20}{t / max(t + f_p, 1):>11.2%}{t / max(t + f_n, 1):>9.2%}{t + f_n:>5}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
