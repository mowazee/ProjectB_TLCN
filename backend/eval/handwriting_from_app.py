"""Độ chính xác OCR chữ viết tay (P2-03, NFR-08) đo từ chính dữ liệu trong ứng dụng.

Quy trình (không cần tự viết file *.gt.txt):
  1. Upload ảnh/PDF chữ viết tay, tick "Chữ viết tay" -> OCR tự chạy bằng engine chữ viết tay.
  2. Mở OCR Editor từng trang, sửa text cho ĐÚNG HOÀN TOÀN với bản gốc (kể cả dấu, xuống dòng) rồi Lưu.
  3. Chạy:  python eval/handwriting_from_app.py            (mặc định: database của demo)
            python eval/handwriting_from_app.py --database-url postgresql+psycopg://...

Text OCR thô (ocr_results.raw_text) là kết quả máy; bản sửa mới nhất (ocr_corrections) là đáp án.
Chỉ tính trang của tài liệu is_handwritten có bản sửa MỚI HƠN lần OCR gần nhất (chạy lại OCR sau khi sửa
thì bản sửa cũ không còn khớp). Trang chưa sửa không có đáp án nên không tính.
Lưu ý: trang sửa chưa kỹ làm con số đẹp hơn thực tế. Con số báo cáo chính thức vẫn nên tách tập test
riêng như eval/README.md; số liệu ở đây dùng để theo dõi và so sánh engine.
"""

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from metrics import char_accuracy, corpus_cer, corpus_wer  # noqa: E402

DEMO_URL = "postgresql+psycopg://postgres@127.0.0.1:55434/dms_demo"
TARGET = 0.70  # D-06: chữ viết tay > 70%

QUERY = """
SELECT d.title, p.page_number, r.raw_text, r.engine_version, c.corrected_text
FROM documents d
JOIN document_pages p ON p.document_id = d.id
JOIN LATERAL (
    SELECT raw_text, engine_version, created_at FROM ocr_results WHERE page_id = p.id
    ORDER BY created_at DESC LIMIT 1
) r ON true
JOIN LATERAL (
    SELECT corrected_text, edited_at FROM ocr_corrections WHERE page_id = p.id
    ORDER BY version DESC LIMIT 1
) c ON c.edited_at >= r.created_at
WHERE d.is_handwritten AND d.lifecycle_status = 'active'
ORDER BY d.title, p.page_number
"""
COUNT_HW_PAGES = """
SELECT count(*) FROM documents d JOIN document_pages p ON p.document_id = d.id
WHERE d.is_handwritten AND d.lifecycle_status = 'active'
"""


@dataclass
class PageRow:
    title: str
    page: int
    engine: str
    truth: str
    ocr: str


@dataclass
class EngineSummary:
    engine: str
    pages: int
    chars: int
    accuracy: float  # 1 - CER gộp (corpus), D-06
    wer: float
    passed: bool


def summarize(rows: list[PageRow]) -> list[EngineSummary]:
    """Gộp theo engine_version: CER/WER gộp trên toàn bộ ký tự (trang dài nặng hơn trang ngắn)."""
    by_engine: dict[str, list[PageRow]] = defaultdict(list)
    for r in rows:
        by_engine[r.engine].append(r)
    out = []
    for engine, items in sorted(by_engine.items()):
        pairs = [(r.truth, r.ocr) for r in items]
        acc = max(0.0, 1.0 - corpus_cer(pairs))
        out.append(
            EngineSummary(
                engine=engine,
                pages=len(items),
                chars=sum(len(r.truth) for r in items),
                accuracy=acc,
                wer=corpus_wer(pairs),
                passed=acc > TARGET,
            )
        )
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--database-url", default=DEMO_URL, help=f"mặc định: database demo ({DEMO_URL})")
    args = ap.parse_args()

    from sqlalchemy import create_engine, text

    with create_engine(args.database_url).connect() as conn:
        rows = [
            PageRow(t, n, ev or "?", truth or "", raw or "") for t, n, raw, ev, truth in conn.execute(text(QUERY)).all()
        ]
        total_hw_pages = conn.execute(text(COUNT_HW_PAGES)).scalar() or 0

    print(f"Trang chữ viết tay: {total_hw_pages}; đã sửa (có đáp án): {len(rows)}")
    if not rows:
        print("Chưa có trang nào để đo: upload tài liệu chữ viết tay rồi sửa text trong OCR Editor (xem đầu file).")
        return 1
    print(f"\n{'tài liệu':<40}{'trang':>6}{'ký tự':>8}{'độ chính xác':>15}")
    for r in rows:
        print(f"{r.title[:39]:<40}{r.page:>6}{len(r.truth):>8}{char_accuracy(r.truth, r.ocr):>15.1%}")
    summaries = summarize(rows)
    print(f"\n{'engine':<32}{'trang':>6}{'ký tự':>8}{'độ chính xác':>15}{'WER':>8}   mục tiêu > {TARGET:.0%}")
    for s in summaries:
        verdict = "ĐẠT" if s.passed else "CHƯA ĐẠT"
        print(f"{s.engine:<32}{s.pages:>6}{s.chars:>8}{s.accuracy:>15.1%}{s.wer:>8.1%}   {verdict}")
    if len(rows) < 30:
        print(
            f"\nLưu ý: mới {len(rows)} trang; đề xuất >= 30 trang trước khi dùng làm số liệu báo cáo (eval/README.md)."
        )

    reports = Path(__file__).resolve().parent / "reports"
    reports.mkdir(exist_ok=True)
    path = reports / f"handwriting_app_{datetime.now():%Y%m%d_%H%M%S}.json"
    path.write_text(
        json.dumps(
            {
                "summary": [asdict(s) for s in summaries],
                "pages": [
                    {"title": r.title, "page": r.page, "engine": r.engine, "accuracy": char_accuracy(r.truth, r.ocr)}
                    for r in rows
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nĐã ghi {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
