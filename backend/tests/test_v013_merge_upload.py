"""FR-16 (SDD v0.13): tải lên nhiều ảnh/PDF gộp thành một tài liệu (một PDF, một job OCR)."""

import uuid
from io import BytesIO

import pymupdf
from PIL import Image
from sqlalchemy import func, select

from app.modules.audit.infrastructure.models import AuditLog
from app.modules.documents.infrastructure.models import Document
from app.modules.jobs.infrastructure.models import ProcessingJob
from app.shared.storage import get_storage
from tests.conftest import make_pdf, make_png


def _post(client, category_id, parts, **form):
    files = [("files", (name, data, "application/octet-stream")) for name, data in parts]
    return client.post("/api/documents", data={"category_id": str(category_id), **form}, files=files)


def test_merge_keeps_order_and_creates_one_document(seed, login, db):
    c = login("officer")
    parts = [
        ("trang1.png", make_png("Trang một", size=(800, 400))),
        ("phan2.pdf", make_pdf(["Nội dung PDF"], pages=2)),
        ("trang4.jpg", make_png("Trang bốn")),
    ]
    # file thứ ba là JPG thật
    buf = BytesIO()
    Image.open(BytesIO(parts[2][1])).convert("RGB").save(buf, format="JPEG")
    parts[2] = ("trang4.jpg", buf.getvalue())

    r = _post(c, seed["category"].id, parts, title="Hồ sơ gộp")
    assert r.status_code == 201, r.text
    doc = db.get(Document, uuid.UUID(r.json()["document_id"]))
    assert doc.mime_type == "application/pdf" and doc.file_name == "trang1.pdf" and doc.title == "Hồ sơ gộp"
    pdf = pymupdf.open(stream=get_storage().read_bytes(doc.storage_key), filetype="pdf")
    assert pdf.page_count == 4
    texts = [" ".join(pdf[i].get_text().split()) for i in (1, 2)]
    assert "(trang 1)" in texts[0] and "(trang 2)" in texts[1]
    assert abs(pdf[0].rect.width - 595) < 1 and abs(pdf[3].rect.width - 595) < 1  # ảnh chuẩn hóa khổ A4
    jobs = db.scalar(select(func.count()).select_from(ProcessingJob).where(ProcessingJob.document_id == doc.id))
    assert jobs == 1
    log = db.scalar(select(AuditLog).where(AuditLog.action == "upload_document", AuditLog.document_id == doc.id))
    assert log.state_after["merged_files"] == 3 and log.state_after["pages"] == 4


def test_merge_rejects_whole_request_when_one_file_is_bad(seed, login, db):
    c = login("officer")
    before = db.scalar(select(func.count()).select_from(Document))
    r = _post(c, seed["category"].id, [("a.png", make_png()), ("xau.pdf", b"not a pdf at all")])
    assert r.status_code in (400, 415) and "xau.pdf" in r.json()["error"]["message"]
    assert db.scalar(select(func.count()).select_from(Document)) == before


def test_merge_limits_and_conflicts(seed, login, monkeypatch):
    from app.shared.config import settings

    c = login("officer")
    monkeypatch.setattr(settings, "MAX_MERGE_FILES", 2)
    r = _post(c, seed["category"].id, [(f"{i}.png", make_png()) for i in range(3)])
    assert r.status_code == 422 and r.json()["error"]["code"] == "TOO_MANY_FILES"
    both = c.post(
        "/api/documents",
        data={"category_id": str(seed["category"].id)},
        files=[("file", ("a.png", make_png(), "image/png")), ("files", ("b.png", make_png(), "image/png"))],
    )
    assert both.status_code == 422
    none = c.post("/api/documents", data={"category_id": str(seed["category"].id)})
    assert none.status_code == 422
