"""Hiệu chỉnh NEEDS_REVIEW_THRESHOLD trên tập DEV (NFR-08): chọn ngưỡng confidence để bắt các trang
có độ chính xác ước tính dưới mục tiêu D-06.

    python eval/calibrate_threshold.py eval/reports/ocr_dev_print_*.json --target 0.90 --min-recall 0.9

Trang "xấu" = 1 - CER < target. Với mỗi ngưỡng t, trang có confidence < t bị đặt needs_review.
recall = tỉ lệ trang xấu bị bắt; review_rate = tỉ lệ trang phải xem lại. Chọn t nhỏ nhất đạt min-recall.
Chỉ dùng tập dev; con số báo cáo cuối lấy từ tập test (ocr_eval.py --split test).
"""

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("report", type=Path)
    ap.add_argument("--target", type=float, default=0.90)
    ap.add_argument("--min-recall", type=float, default=0.90)
    args = ap.parse_args()
    data = json.loads(args.report.read_text(encoding="utf-8"))
    if data.get("split") != "dev":
        print("! Nên hiệu chỉnh trên tập dev, không dùng tập test")
    pages = [p for p in data["pages"] if p["confidence"] is not None]
    if not pages:
        print("Không có trang OCR (có confidence) trong báo cáo")
        return 2
    bad = [p for p in pages if 1 - p["cer"] < args.target]
    print(f"{len(pages)} trang OCR, {len(bad)} trang dưới mục tiêu {args.target:.0%}")
    print(f"{'ngưỡng':>8}{'recall':>9}{'review_rate':>13}")
    chosen = None
    for t in range(50, 100):
        flagged = [p for p in pages if p["confidence"] < t]
        recall = sum(1 for p in bad if p["confidence"] < t) / len(bad) if bad else 1.0
        rate = len(flagged) / len(pages)
        if t % 5 == 0:
            print(f"{t:>8}{recall:>9.2%}{rate:>13.2%}")
        if chosen is None and recall >= args.min_recall:
            chosen = (t, recall, rate)
    if chosen:
        print(f"Đề xuất NEEDS_REVIEW_THRESHOLD={chosen[0]} (recall {chosen[1]:.0%}, xem lại {chosen[2]:.0%} số trang)")
    else:
        print("Không ngưỡng nào đạt min-recall; xem lại engine/tiền xử lý")
    return 0


if __name__ == "__main__":
    sys.exit(main())
