"""Top-1 accuracy phân loại (P2-05): scikit-learn TF-IDF + Logistic Regression, chia train/test cố định.

    python eval/classification_eval.py eval/data/classification.jsonl --test-ratio 0.3

Mỗi dòng JSONL: {"text": "...", "category": "HOP-DONG"}. Xáo trộn với seed cố định rồi chia.
Bảng cuối giúp chọn CLASSIFY_MIN_SCORE (UC-22 bước 2a: điểm cao nhất dưới ngưỡng → không gợi ý):
ở mỗi ngưỡng, "độ phủ" = tỉ lệ tài liệu còn được gợi ý, "top-1" = độ chính xác trên các tài liệu đó.
"""

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.modules.classification.infrastructure.sklearn_classifier import MODEL_NAME, train  # noqa: E402

THRESHOLDS = (0.0, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("data", type=Path)
    ap.add_argument("--test-ratio", type=float, default=0.3)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    rows = [json.loads(x) for x in args.data.read_text(encoding="utf-8").splitlines() if x.strip()]
    random.Random(args.seed).shuffle(rows)
    cut = int(len(rows) * (1 - args.test_ratio))
    labels = sorted({r["category"] for r in rows})
    idx = {c: i for i, c in enumerate(labels)}
    model = train((idx[r["category"]], r["text"]) for r in rows[:cut])
    test = rows[cut:]
    correct, top3 = 0, 0
    confusion: Counter[tuple[str, str]] = Counter()
    scored: list[tuple[float, bool]] = []
    for r in test:
        pred = model.predict(r["text"], top_k=3)
        best = labels[pred[0][0]] if pred else "-"
        ok = best == r["category"]
        correct += ok
        top3 += r["category"] in [labels[p[0]] for p in pred]
        scored.append((pred[0][1] if pred else 0.0, ok))
        if not ok:
            confusion[(r["category"], best)] += 1
    n = max(len(test), 1)
    print(f"model={MODEL_NAME} train={cut} test={len(test)} nhãn={len(labels)}")
    print(f"top-1 accuracy: {correct / n:.2%}   top-3: {top3 / n:.2%}")
    for (gold, wrong), k in confusion.most_common(10):
        print(f"  nhầm {gold} -> {wrong}: {k}")
    print("ngưỡng  độ phủ  top-1 (trong phần được gợi ý)")
    for t in THRESHOLDS:
        kept = [ok for score, ok in scored if score >= t]
        acc = sum(kept) / len(kept) if kept else 0.0
        print(f"  {t:4.2f}  {len(kept) / n:6.1%}  {acc:6.1%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
