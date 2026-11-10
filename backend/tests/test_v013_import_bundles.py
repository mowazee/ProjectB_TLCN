"""FR-15 + P2-08 (SDD v0.14): nhập hàng loạt chỉ theo manifest.csv, có tài liệu đi kèm."""

import io
import zipfile
from uuid import UUID

import pytest
from sqlalchemy import select

from app.modules.documents.infrastructure.models import Document, DocumentAttachment
from app.modules.imports.domain.archive import ArchiveError, Entry
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


def test_group_manifest_only():
    """v0.14: chỉ manifest.csv - bắt buộc; file không khai báo bị bỏ qua (NOT_IN_MANIFEST)."""
    e = lambda n: Entry(n, data=b"x")  # noqa: E731
    entries = [e("lo.zip/HS1/main.pdf"), e("lo.zip/HS1/dinh-kem/a.docx"), e("le.pdf"), e("thua.pdf")]
    with pytest.raises(ArchiveError) as err:
        group(entries, None)
    assert err.value.code == "MANIFEST_REQUIRED"
    manifest = b"file_name,attachments\nmain.pdf,a.docx\nle.pdf,\n"
    bundles, loose = group(entries, manifest)
    by = {b.key: b for b in bundles}
    assert [a.filename for a in by["lo.zip/HS1/main.pdf"].attachments] == ["a.docx"]
    assert "le.pdf" in by
    assert [(x.name, x.error_code) for x in loose] == [("thua.pdf", "NOT_IN_MANIFEST")]


def test_import_manifest_bundles(seed, login, db, enqueued):
    c = login("officer", features=F)
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


def test_manifest_file_name_merges_multiple_files(seed, login, db, enqueued):
    """v0.15: file_name liệt kê nhiều file (;) -> gộp một PDF theo thứ tự khai báo; tên file PDF và tiêu đề lấy theo
    title, title trống thì theo tên file đầu tiên."""
    c = login("officer", features=F)
    manifest = ("file_name,title\ntrang2.png;trang1.png,\na.pdf;b.png,Hồ sơ: gộp/01\nx.png;khong-co.png,\n").encode()
    files = [
        ("files", ("trang1.png", make_png("Trang 1"), "x")),
        ("files", ("trang2.png", make_png("Trang 2"), "x")),
        ("files", ("a.pdf", make_pdf(["A"]), "x")),
        ("files", ("b.png", make_png("B"), "x")),
        ("files", ("x.png", make_png("X"), "x")),
        ("files", ("manifest.csv", manifest, "text/csv")),
    ]
    r = c.post("/api/imports", data={"category_id": str(seed["category"].id)}, files=files)
    job_id = UUID(r.json()["job_id"])
    assert run_job(job_id).value == "completed"
    by = {f["name"]: f for f in c.get(f"/api/imports/{job_id}").json()["files"]}
    assert by["trang2.png"]["status"] == "imported" and by["a.pdf"]["status"] == "imported"
    assert by["x.png"]["code"] == "FILE_NOT_FOUND"
    db.rollback()
    first = db.get(Document, UUID(by["trang2.png"]["document_id"]))  # title trống: theo file đầu tiên
    assert (first.mime_type, first.file_name, first.title) == ("application/pdf", "trang2.pdf", "trang2")
    named = db.get(Document, UUID(by["a.pdf"]["document_id"]))  # có title: tên file PDF theo title (bỏ ký tự cấm)
    assert named.title == "Hồ sơ: gộp/01" and named.file_name == "Hồ sơ  gộp 01.pdf"


def test_template_zip_has_manifest_and_guide(seed, login):
    r = login("officer", features=F).get("/api/imports/template.zip")
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        assert sorted(zf.namelist()) == ["HUONG-DAN.txt", "manifest.csv"]
        csv_text = zf.read("manifest.csv").decode("utf-8-sig")
        assert csv_text.startswith("file_name,attachments,title,category,document_code,validity,valid_until")
        assert "trang-1.jpg;trang-2.jpg" in csv_text
        assert "GỘP" in zf.read("HUONG-DAN.txt").decode("utf-8-sig")
