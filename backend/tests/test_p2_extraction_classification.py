"""P2-04 trích xuất trường (UC-21) và P2-05 phân loại tự động (UC-22)."""

import uuid
from types import SimpleNamespace

from sqlalchemy import func, select

from app.modules.audit.infrastructure.models import AuditLog
from app.modules.classification.application.suggest import enqueue_classification
from app.modules.classification.infrastructure import sklearn_classifier
from app.modules.extraction.domain import rules
from app.modules.extraction.infrastructure.models import DocumentExtractedField
from app.modules.ocr.domain.ports import OcrLine
from tests.conftest import make_png, run_all_jobs, upload

CONG_VAN = [
    "UY BAN NHAN DAN TINH BINH DUONG",
    "Số: 123/2026/QĐ-UBND",
    "Bình Dương, ngày 05 tháng 3 năm 2026",
    "V/v: triển khai số hóa hồ sơ lưu trữ",
    "CHỦ TỊCH",
    "Nguyễn Văn An",
]
HOP_DONG = [
    "HỢP ĐỒNG MUA BÁN HÀNG HÓA",
    "Số: 45/2026/HĐMB",
    "BÊN A (Bên bán): Công ty TNHH ABC",
    "BÊN B (Bên mua): Công ty Cổ phần XYZ",
    "Giá trị hợp đồng: 150.000.000 VND",
    "hai bên thỏa thuận mua bán hàng hóa, giao hàng, thanh toán",
]


def _lines(texts: list[str]) -> list[OcrLine]:
    return [OcrLine(t, 0.95, (10, 10 + 30 * i, 400, 25)) for i, t in enumerate(texts)]


# ---------------------------------------------------------------- P2-04
def test_rules_unit():
    got = {e.name: e.value for e in rules.extract("\n".join(CONG_VAN), "CONG-VAN")}
    assert got["so_hieu"] == "123/2026/QĐ-UBND"
    assert got["ngay_ban_hanh"] == "2026-03-05"
    assert got["trich_yeu"] == "triển khai số hóa hồ sơ lưu trữ"
    assert got["co_quan_ban_hanh"] == "UY BAN NHAN DAN TINH BINH DUONG"
    assert got["nguoi_ky"] == "Nguyễn Văn An"
    hd = {e.name: e.value for e in rules.extract("\n".join(HOP_DONG), "HOP-DONG")}
    assert hd["ben_a"] == "Công ty TNHH ABC" and hd["ben_b"] == "Công ty Cổ phần XYZ"
    assert hd["gia_tri"] == "150.000.000 VND" and hd["so_hieu"] == "45/2026/HĐMB"
    no_accent = {e.name: e.value for e in rules.extract("So: 9/2025/TB-BGD\nngay 1/2/2025", None)}
    assert no_accent == {"so_hieu": "9/2025/TB-BGD", "ngay_ban_hanh": "2025-02-01"}


def test_extraction_flow(seed, login, db, fake_engine, enqueued):
    fake_engine.lines = _lines(CONG_VAN)
    c = login("officer", features="extraction")
    doc_id = upload(c, seed["category2"].id, make_png(), "cv.png").json()["document_id"]
    run_all_jobs(enqueued)  # OCR -> OcrCompleted -> job EXTRACT
    body = c.get(f"/api/documents/{doc_id}/fields").json()
    assert body["job_status"] == "completed"
    fields = {f["field_name"]: f for f in body["items"]}
    assert fields["so_hieu"]["field_value"] == "123/2026/QĐ-UBND" and fields["so_hieu"]["is_verified"] is False
    assert fields["so_hieu"]["label"] == "Số, ký hiệu" and fields["so_hieu"]["extracted_method"] == "regex-v1"

    r = c.put(f"/api/documents/{doc_id}/fields/so_hieu", json={"field_value": "123/2026/QĐ-UBND"})
    assert r.json()["is_verified"] is True and r.json()["extracted_method"] == "regex-v1"
    r = c.put(f"/api/documents/{doc_id}/fields/nguoi_ky", json={"field_value": "Nguyễn Văn Bình"})
    assert r.json()["extracted_method"] == "manual"

    # Chạy lại: không trùng, không ghi đè trường đã xác nhận
    assert c.post(f"/api/documents/{doc_id}/fields/extract").status_code == 202
    run_all_jobs(enqueued)
    db.rollback()
    assert db.scalar(select(func.count(DocumentExtractedField.id))) == len(
        [f for f in body["items"] if f["field_value"]]
    )
    after = {f["field_name"]: f for f in c.get(f"/api/documents/{doc_id}/fields").json()["items"]}
    assert after["nguoi_ky"]["field_value"] == "Nguyễn Văn Bình"
    actions = set(db.scalars(select(AuditLog.action).where(AuditLog.module == "extraction")).all())
    assert {"verify_field", "update_field", "request_extraction"} <= actions
    assert c.put(f"/api/documents/{doc_id}/fields/khong_co", json={}).status_code == 404
    approver = login("approver", features="extraction")
    assert approver.get(f"/api/documents/{doc_id}/fields").status_code == 200
    assert approver.put(f"/api/documents/{doc_id}/fields/so_hieu", json={}).status_code == 403


# ---------------------------------------------------------------- P2-05
def test_sklearn_classifier_unit():
    model = sklearn_classifier.train(
        [
            (1, "hợp đồng mua bán bên a bên b giá trị thanh toán"),
            (1, "hợp đồng thuê nhà bên cho thuê bên thuê"),
            (2, "công văn ủy ban nhân dân v/v triển khai kế hoạch"),
            (2, "quyết định của chủ tịch ủy ban về việc bổ nhiệm"),
            (3, "hóa đơn giá trị gia tăng thuế suất tổng cộng"),
        ]
    )
    assert model.name == sklearn_classifier.MODEL_NAME and model.n_docs == 5
    # OCR mất dấu vẫn khớp mẫu có dấu (tokenizer bỏ dấu)
    top = model.predict("HOP DONG mua ban giua ben A va ben B")
    assert [c for c, _ in top][0] == 1 and len(top) == 3
    assert top[0][1] > top[1][1] >= top[2][1] and abs(sum(p for _, p in top) - 1) < 1e-6
    assert model.predict("") == [] and model.predict("a , .") == []


def test_sklearn_classifier_needs_two_categories():
    assert sklearn_classifier.train([]).predict("hợp đồng") == []
    single = sklearn_classifier.train([(7, "hợp đồng mua bán")])
    assert single.predict("hợp đồng thuê") == [(7, 1.0)]


def test_classification_threshold_applies_to_top_score_only(seed, login, db, fake_engine, enqueued, monkeypatch):
    # UC-22 2a: điểm cao nhất dưới ngưỡng -> không gợi ý; đạt ngưỡng -> trả đủ tối đa 3 gợi ý
    from app.shared.config import settings

    c = login("officer", features="classification")
    fake_engine.lines = _lines(HOP_DONG)
    doc_id = upload(c, seed["category2"].id, make_png(), "hd.png").json()["document_id"]
    monkeypatch.setattr(settings, "CLASSIFY_MIN_SCORE", 0.99)
    run_all_jobs(enqueued)
    assert c.get(f"/api/documents/{doc_id}/category-suggestions").json()["items"] == []

    monkeypatch.setattr(settings, "CLASSIFY_MIN_SCORE", 0.0)
    enqueue_classification(SimpleNamespace(document_id=uuid.UUID(doc_id)))  # như khi OcrCompleted chạy lại
    run_all_jobs(enqueued)
    items = c.get(f"/api/documents/{doc_id}/category-suggestions").json()["items"]
    assert len(items) == 2  # 2 danh mục đang dùng trong seed -> trả cả hai, kể cả gợi ý điểm thấp
    assert items[0]["category_id"] == seed["category"].id


def test_classification_flow(seed, login, db, fake_engine, enqueued):
    c = login("officer", features="classification")
    fake_engine.lines = _lines(HOP_DONG)
    upload(c, seed["category"].id, make_png(), "hd1.png")  # mẫu đã gán Hợp đồng
    run_all_jobs(enqueued)
    fake_engine.lines = _lines(CONG_VAN)
    upload(c, seed["category2"].id, make_png(), "cv1.png")  # mẫu Công văn
    run_all_jobs(enqueued)
    fake_engine.lines = _lines(HOP_DONG[:1] + HOP_DONG[2:])
    doc_id = upload(c, seed["category2"].id, make_png(), "nham.png").json()["document_id"]  # chọn nhầm
    run_all_jobs(enqueued)

    body = c.get(f"/api/documents/{doc_id}/category-suggestions").json()
    assert body["job_status"] == "completed" and 1 <= len(body["items"]) <= 3
    top = body["items"][0]
    assert top["category_id"] == seed["category"].id and top["is_current"] is False
    assert c.get(f"/api/documents/{doc_id}").json()["category"]["name"] == "Công văn"  # không tự ghi đè

    bad = c.post(f"/api/documents/{doc_id}/category-suggestions/accept", json={"category_id": 999})
    assert bad.status_code == 422
    r = c.post(f"/api/documents/{doc_id}/category-suggestions/accept", json={"category_id": seed["category"].id})
    assert r.status_code == 200 and r.json()["is_current"] is True
    assert c.get(f"/api/documents/{doc_id}").json()["category"]["name"] == "Hợp đồng"
    db.rollback()
    log = db.scalar(select(AuditLog).where(AuditLog.action == "accept_category_suggestion"))
    assert log.state_after["score"] == top["score"]

    # chỉ gợi ý danh mục đang dùng
    login("admin", features="classification").patch(f"/api/categories/{seed['category'].id}", json={"is_active": False})
    ids = [s["category_id"] for s in c.get(f"/api/documents/{doc_id}/category-suggestions").json()["items"]]
    assert seed["category"].id not in ids
