"""FR-15 + P2-08 (SDD v0.13): nhập hàng loạt theo quy ước thư mục / manifest.csv có tài liệu đi kèm."""

import io
import zipfile
from uuid import UUID

from sqlalchemy import select

from app.modules.documents.infrastructure.models import Document, DocumentAttachment
from app.modules.imports.domain.archive import Entry
from app.modules.imports.domain.bundles import group
from app.modules.jobs.application.runner import run_job
from tests.conftest import make_pdf, make_png

F = "imports"
TXT = "Ghi chú".encode()


def _zip(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


def test_group_folder_convention():
    e = lambda n: Entry(n, data=b"x")  # noqa: E731
    entries = [
        e("lo.zip/HS1/main.pdf"),
        e("lo.zip/HS1/khac.pdf"),
        e("lo.zip/HS1/dinh-kem/a.docx"),
        e("lo.zip/HS2/1.png"),
        e("lo.zip/HS2/2.jpg"),
        e("lo.zip/HS2/dinh-kem/b.txt"),
        e("lo.zip/HS3/x.pdf"),
        e("lo.zip/HS3/y.pdf"),
        e("lo.zip/HS3/dinh-kem/c.txt"),
        e("lo.zip/thuong/z.pdf"),  # thư mục thường: nhập riêng như trước
        e("le.pdf"),
    ]
    bundles, loose = group(entries, None)
    by = {b.key: b for b in bundles}
    assert [m.filename for m in by["lo.zip/HS1"].main] == ["main.pdf"]
    assert [a.filename for a in by["lo.zip/HS1"].attachments] == ["a.docx"]
    assert [m.filename for m in by["lo.zip/HS2"].main] == ["1.png", "2.jpg"]
    assert by["lo.zip/HS3"].error_code == "BUNDLE_NO_MAIN"
    assert sorted(x.name for x in loose) == ["le.pdf", "lo.zip/HS1/khac.pdf", "lo.zip/thuong/z.pdf"]


def test_import_folder_bundles_and_manifest(seed, login, db, enqueued):
    c = login("officer", features=F)
    archive = _zip(
        {
            "HS1/main.pdf": make_pdf(["Ho so 1"]),
            "HS1/dinh-kem/phu-luc.txt": TXT,
            "HS2/trang1.png": make_png("Trang 1"),
            "HS2/trang2.png": make_png("Trang 2"),
            "HS2/dinh-kem/ghi-chu.txt": TXT,
            "HS3/a.pdf": make_pdf(["a"]),
            "HS3/b.pdf": make_pdf(["b"]),
            "HS3/dinh-kem/x.txt": TXT,
        }
    )
    r = c.post(
        "/api/imports", data={"category_id": str(seed["category"].id)}, files=[("files", ("lo.zip", archive, "x"))]
    )
    job_id = UUID(r.json()["job_id"])
    assert run_job(job_id).value == "completed"
    rep = c.get(f"/api/imports/{job_id}").json()
    by = {f["name"]: f for f in rep["files"]}
    assert by["lo.zip/HS1"]["status"] == "imported" and by["lo.zip/HS1"]["attachments"] == 1
    assert by["lo.zip/HS2"]["status"] == "imported"
    assert by["lo.zip/HS3"]["code"] == "BUNDLE_NO_MAIN"
    db.rollback()
    hs2 = db.get(Document, UUID(by["lo.zip/HS2"]["document_id"]))
    assert hs2.mime_type == "application/pdf"  # 2 ảnh gộp thành một PDF

    # manifest.csv: file chính + nhiều file đi kèm; thiếu file đi kèm chỉ làm lỗi bộ đó
    manifest = (
        "file_name,attachments,title,document_code\n"
        "qd.pdf,pl1.txt;pl2.txt,Quyết định 12,12/QĐ\n"
        "cv.pdf,khong-co.txt,Công văn,\n"
    ).encode()
    files = [
        ("files", ("qd.pdf", make_pdf(["QD"]), "x")),
        ("files", ("pl1.txt", TXT, "x")),
        ("files", ("pl2.txt", TXT, "x")),
        ("files", ("cv.pdf", make_pdf(["CV"]), "x")),
        ("files", ("manifest.csv", manifest, "text/csv")),
    ]
    r = c.post("/api/imports", data={"category_id": str(seed["category"].id)}, files=files)
    job_id = UUID(r.json()["job_id"])
    assert run_job(job_id).value == "completed"
    rep = c.get(f"/api/imports/{job_id}").json()
    by = {f["name"]: f for f in rep["files"]}
    assert by["qd.pdf"]["status"] == "imported" and by["qd.pdf"]["attachments"] == 2
    assert by["cv.pdf"]["code"] == "ATTACHMENT_NOT_FOUND"
    db.rollback()
    doc = db.get(Document, UUID(by["qd.pdf"]["document_id"]))
    assert doc.title == "Quyết định 12" and doc.document_code == "12/QĐ"
    names = set(db.scalars(select(DocumentAttachment.file_name).where(DocumentAttachment.document_id == doc.id)))
    assert names == {"pl1.txt", "pl2.txt"}


def test_manifest_validity_columns_fr19(seed, login, db, enqueued):
    """FR-19 (SDD v0.14): manifest.csv có cột validity, valid_until; giá trị sai chỉ làm lỗi bộ đó."""
    c = login("officer", features=F)
    manifest = (
        "file_name,title,validity,valid_until\n"
        "a.pdf,Còn hiệu lực đến,effective_until,31/12/2099\n"
        "b.pdf,Sai hiệu lực,khong-hop-le,\n"
        "c.pdf,Không khai báo,,\n"
    ).encode()
    files = [("files", (n, make_pdf([n]), "x")) for n in ("a.pdf", "b.pdf", "c.pdf")]
    files.append(("files", ("manifest.csv", manifest, "text/csv")))
    r = c.post("/api/imports", data={"category_id": str(seed["category"].id)}, files=files)
    job_id = UUID(r.json()["job_id"])
    assert run_job(job_id).value == "completed"
    by = {f["name"]: f for f in c.get(f"/api/imports/{job_id}").json()["files"]}
    assert by["b.pdf"]["code"] == "VALIDITY_INVALID"
    db.rollback()
    a = db.get(Document, UUID(by["a.pdf"]["document_id"]))
    assert str(a.validity_status) == "effective_until" and a.valid_until.isoformat() == "2099-12-31"
    assert str(db.get(Document, UUID(by["c.pdf"]["document_id"])).validity_status) == "unspecified"
