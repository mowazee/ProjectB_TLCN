"""P2-03: đo độ chính xác chữ viết tay từ dữ liệu trong ứng dụng (eval/handwriting_from_app.py)."""

import sys
from pathlib import Path

import pytest
from sqlalchemy import text

from app.modules.ocr.application import engines
from app.modules.ocr.domain.ports import OcrLine
from tests.conftest import FakeEngine, make_png, run_all_jobs, upload

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "eval"))

from handwriting_from_app import QUERY, TARGET, PageRow, summarize  # noqa: E402


def test_summarize_groups_by_engine_and_checks_target():
    rows = [
        PageRow("A", 1, "vietocr 0.3.13", "Hôm nay tôi đi họp", "Hôm nay tôi đi họp"),
        PageRow("A", 2, "vietocr 0.3.13", "Biên bản", "Biên bàn"),
        PageRow("B", 1, "paddleocr-hw 3.7.0", "Hôm nay", "Hom nay"),  # mất 1 dấu / 7 ký tự
        PageRow("C", 1, "paddleocr-hw 3.7.0", "Ngày", "xxxxxxxx"),
    ]
    by = {s.engine: s for s in summarize(rows)}
    viet = by["vietocr 0.3.13"]
    assert viet.pages == 2 and viet.chars == 26 and viet.accuracy == pytest.approx(1 - 1 / 26) and viet.passed
    paddle = by["paddleocr-hw 3.7.0"]
    assert paddle.pages == 2 and paddle.accuracy < TARGET and not paddle.passed  # CER gộp: trang hỏng kéo cả nhóm


def test_query_pairs_raw_ocr_with_newer_correction(seed, login, db, enqueued, fake_engine):
    if db.get_bind().dialect.name != "postgresql":
        pytest.skip("câu truy vấn dùng LATERAL của PostgreSQL (CI backend chạy trên PostgreSQL 18)")
    hw = FakeEngine()
    hw.name, hw.version = "hw-fake", "0.1"
    hw.lines = [OcrLine("Hom nay toi di hop", 0.8, (10, 10, 300, 30))]
    engines.override("handwriting", hw)
    c = login("officer", features="handwriting")
    doc = upload(c, seed["category"].id, make_png(), "hw.png", title="Thư tay", is_handwritten="true").json()
    upload(c, seed["category"].id, make_png(), "print.png", title="Chữ in")  # không phải chữ viết tay: bỏ qua
    run_all_jobs(enqueued)
    enqueued.clear()

    def rows():
        db.rollback()  # thấy dữ liệu API vừa ghi
        result = db.execute(text(QUERY)).all()
        db.rollback()  # đóng transaction đọc: không giữ khóa bảng khi test dọn dữ liệu
        return result

    assert rows() == []  # chưa sửa -> chưa có đáp án
    doc_id = doc["document_id"]
    put = c.put(
        f"/api/documents/{doc_id}/pages/1/correction", json={"corrected_text": "Hôm nay tôi đi họp", "base_version": 0}
    )
    assert put.status_code == 200
    got = rows()
    assert [(t, n, raw, ev, truth) for t, n, raw, ev, truth in got] == [
        ("Thư tay", 1, "Hom nay toi di hop", "hw-fake 0.1", "Hôm nay tôi đi họp")
    ]

    # Chạy lại OCR sau khi sửa: bản sửa cũ không khớp lần OCR mới -> không tính
    assert c.post(f"/api/documents/{doc_id}/reprocess", json={"ocr_profile": "handwriting"}).status_code == 202
    run_all_jobs(enqueued)
    assert rows() == []
