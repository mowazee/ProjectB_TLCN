"""FR-04 (SDD v0.9): trang PDF có lớp chữ vẫn OCR phần chữ nằm trong ảnh nhúng."""

from uuid import UUID

import pymupdf
from sqlalchemy import select

from app.modules.documents.infrastructure.models import DocumentPage
from app.modules.jobs.application.runner import run_job
from app.modules.jobs.domain.model import JobOutcome
from app.modules.jobs.infrastructure.models import ProcessingJob
from app.modules.ocr.application import engines
from app.modules.ocr.domain.ports import OcrLine
from app.modules.ocr.domain.regions import merge_reading_order, regions_to_ocr
from app.modules.ocr.infrastructure.models import OcrResult
from tests.conftest import FONT, make_png, upload

ZOOM = 200 / 72  # OCR_RENDER_DPI mặc định


SIGNATURE = [
    "Người ký: CỔNG THÔNG TIN ĐIỆN TỬ CHÍNH PHỦ",
    "Cơ quan: VĂN PHÒNG CHÍNH PHỦ",
    "Thời gian ký: 10.01.2025 15:20:10 +07:00",
]


def _signed_scan_pdf() -> bytes:
    """Như văn bản ký số thật: trang 1 là ảnh scan phủ cả trang + khối chữ ký số (lớp chữ) nhỏ ở góc trên."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_image(page.rect, stream=make_png("Nội dung bản scan", size=(1190, 1684)))  # đúng tỷ lệ A4
    if FONT:
        page.insert_font(fontname="vn", fontfile=FONT)
    for i, line in enumerate(SIGNATURE):
        page.insert_text((370, 22 + i * 8), line, fontname="vn" if FONT else "helv", fontsize=6)
    return bytes(doc.tobytes())


def _pdf(*, image_rect=None, invisible_scan=False) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    font = "helv"
    if FONT:
        page.insert_font(fontname="vn", fontfile=FONT)
        font = "vn"
    if invisible_scan:
        # Bản scan đã OCR sẵn: ảnh phủ cả trang + lớp chữ ẩn (render_mode=3) nằm trên ảnh
        page.insert_image(page.rect, stream=make_png("Ban scan", size=(1190, 1684)))
        for y in (120, 400, 700):  # lớp chữ ẩn trải khắp trang như phần mềm scan sinh ra
            page.insert_text((72, y), "Văn bản đã OCR sẵn trong bản scan, lớp chữ ẩn", fontname=font, render_mode=3)
        return bytes(doc.tobytes())
    page.insert_text((72, 100), "Dòng đầu trang của lớp chữ số 1", fontname=font, fontsize=12)
    page.insert_text((72, 700), "Dòng cuối trang của lớp chữ số 2", fontname=font, fontsize=12)
    if image_rect:
        page.insert_image(pymupdf.Rect(*image_rect), stream=make_png("Con dấu", size=(800, 400)))
    return bytes(doc.tobytes())


def _run(seed, login, db, data):
    body = upload(login("officer"), seed["category"].id, data, "a.pdf").json()
    doc_id, job_id = UUID(body["document_id"]), UUID(body["job_id"])
    assert run_job(job_id) == JobOutcome.COMPLETED
    db.rollback()
    db.expire_all()
    page = db.scalar(select(DocumentPage).where(DocumentPage.document_id == doc_id))
    result = db.scalar(select(OcrResult).where(OcrResult.page_id == page.id))
    return db.get(ProcessingJob, job_id), page, result


def test_text_layer_page_also_reads_text_inside_embedded_image(seed, login, db, fake_engine):
    fake_engine.lines = [  # chữ trong ảnh đọc kém tin cậy -> trang cần xem lại dù phần lớp chữ chuẩn
        OcrLine("Hop dong so 123/2026", 0.6, (20, 20, 300, 30)),
        OcrLine("Cong ty TNHH ABC", 0.7, (20, 60, 250, 30)),
    ]
    job, page, result = _run(seed, login, db, _pdf(image_rect=(72, 300, 472, 500)))
    assert fake_engine.calls == 1  # đúng một vùng ảnh
    # Thứ tự đọc: dòng trên ảnh, chữ trong ảnh, dòng dưới ảnh
    assert result.raw_text.splitlines() == [
        "Dòng đầu trang của lớp chữ số 1",
        "Hop dong so 123/2026",
        "Cong ty TNHH ABC",
        "Dòng cuối trang của lớp chữ số 2",
    ]
    assert result.engine_version.startswith("pymupdf+fake")
    # Box của chữ trong ảnh đổi về toạ độ trang (FakeEngine trả (20, 20) trong vùng cắt)
    box = next(b["box"] for b in result.boxes if b["text"] == "Hop dong so 123/2026")
    assert box[0] == round(72 * ZOOM) + 20 and box[1] == round(300 * ZOOM) + 20
    assert next(b for b in result.boxes if b["text"].startswith("Dòng đầu"))["score"] is None
    # Confidence chỉ tính trên phần OCR (dưới ngưỡng 85 -> cần xem lại); dòng lớp chữ không kéo điểm lên
    assert result.confidence is not None and float(result.confidence) < 70 and page.ocr_status == "needs_review"
    assert job.result["mixed_pages"] == 1 and job.result["text_layer_pages"] == 0

    # Chữ trong ảnh tìm kiếm được
    hits = login("officer").get("/api/search", params={"q": "TNHH ABC"}).json()
    assert hits["total"] == 1


def test_signed_scan_page_ocrs_scan_content_not_only_signature(seed, login, db, fake_engine):
    sig_y = round(22 * ZOOM)  # dòng chữ ký đầu tiên (pixel)
    fake_engine.lines = [
        OcrLine("Điều 1. Phạm vi điều chỉnh", 0.95, (100, 600, 900, 40)),
        OcrLine("Người ký: CỔNG THÔNG TIN", 0.9, (round(370 * ZOOM) + 5, sig_y - 12, 400, 18)),  # OCR đọc lại chữ ký
    ]
    _, page, result = _run(seed, login, db, _signed_scan_pdf())
    assert fake_engine.calls == 1  # nội dung bản scan được OCR (trước đây chỉ lấy khối chữ ký)
    text = result.raw_text.splitlines()
    assert "Điều 1. Phạm vi điều chỉnh" in text
    assert text.count("Người ký: CỔNG THÔNG TIN ĐIỆN TỬ CHÍNH PHỦ") == 1  # chữ ký giữ từ lớp chữ, không lặp
    assert "Người ký: CỔNG THÔNG TIN" not in text  # dòng OCR trùng vị trí lớp chữ bị bỏ
    assert result.engine_version.startswith("pymupdf+fake")


def test_scan_with_hidden_text_layer_is_not_ocred_again(seed, login, db, fake_engine, monkeypatch):
    loads = []
    real = engines.get_engine
    monkeypatch.setattr(engines, "get_engine", lambda profile: loads.append(profile) or real(profile))
    _, page, result = _run(seed, login, db, _pdf(invisible_scan=True))
    assert fake_engine.calls == 0 and loads == []  # không nạp engine OCR (tốn 2-3 GB RAM) khi không có vùng cần đọc
    assert result.engine_version.startswith("pymupdf ") and page.ocr_status == "completed"


def test_small_image_like_logo_is_skipped(seed, login, db, fake_engine):
    _, _, result = _run(seed, login, db, _pdf(image_rect=(500, 40, 540, 60)))  # 40x20 pt
    assert fake_engine.calls == 0 and result.engine_version.startswith("pymupdf ")


def test_regions_and_reading_order_rules():
    text = [OcrLine("Tiêu đề văn bản hành chính", None, (100, 100, 800, 40))]
    page = (1700, 2200)
    common = {"min_area_ratio": 0.02, "max_regions": 8, "min_text_chars": 20}
    stamp, background, logo = (100, 600, 600, 400), (0, 0, 1700, 2200), (1500, 50, 60, 30)
    body = [OcrLine("Nội dung văn bản trải khắp trang " * 2, None, (100, y, 1400, 40)) for y in (100, 1000, 2000)]
    assert regions_to_ocr([stamp, background, logo], body, *page, **common) == [stamp]  # ảnh nền dưới văn bản: bỏ
    # Chỉ một khối chữ nhỏ (chữ ký số) trên ảnh phủ cả trang: vẫn OCR ảnh
    assert regions_to_ocr([background], text, *page, **common) == [background]
    many = [(0, i * 180, 600, 170) for i in range(12)]  # mỗi vùng ~2,7% trang
    assert len(regions_to_ocr(many, [], *page, **common | {"max_regions": 3})) == 3

    below = OcrLine("Dòng sau ảnh", None, (100, 1200, 500, 40))
    found = [OcrLine("Chữ trong ảnh", 0.9, (150, 650, 300, 30))]
    merged = merge_reading_order([text[0], below], [(stamp, found), ((0, 2000, 10, 10), [])])
    assert [ln.text for ln in merged] == ["Tiêu đề văn bản hành chính", "Chữ trong ảnh", "Dòng sau ảnh"]
