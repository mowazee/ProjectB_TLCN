"""FR-05 (UC-03), FR-06 (UC-04, UC-05a), FR-08 dashboard (UC-07)."""

from sqlalchemy import select

from app.modules.audit.infrastructure.models import AuditLog
from app.modules.ocr.domain.events import CorrectionSaved
from app.modules.search.domain.normalize import fold, normalize_query
from app.shared.events import bus
from tests.conftest import make_pdf, make_png, run_all_jobs, upload


def _processed(seed, login, enqueued, data, name, title=None, user="officer"):
    doc_id = upload(login(user), seed["category"].id, data, name, title=title).json()["document_id"]
    run_all_jobs(enqueued)
    return doc_id


def test_fold_keeps_length():
    text = "Hợp ĐỒNG số 12\nđã ký"
    assert fold(text) == "hop dong so 12 da ky" and len(fold(text)) == len(text)
    assert normalize_query("  HỢP   đồng ") == "hop dong"


def test_correction_versions_and_409(seed, login, db, fake_engine, enqueued):
    doc_id = _processed(seed, login, enqueued, make_png(), "a.png")
    c = login("officer")
    page = c.get(f"/api/documents/{doc_id}/pages/1").json()
    assert page["version"] == 0 and page["can_edit"] and float(page["confidence"]) == 85.0
    raw = page["raw_text"]
    saved = []
    bus.subscribe(CorrectionSaved, saved.append)
    r1 = c.put(f"/api/documents/{doc_id}/pages/1/correction", json={"corrected_text": "Hợp đồng 1", "base_version": 0})
    assert r1.status_code == 200 and r1.json()["version"] == 1 and len(saved) == 1
    stale = c.put(f"/api/documents/{doc_id}/pages/1/correction", json={"corrected_text": "B", "base_version": 0})
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "VERSION_CONFLICT"
    assert stale.json()["error"]["details"]["current_version"] == 1
    page = c.get(f"/api/documents/{doc_id}/pages/1").json()
    assert page["version"] == 1 and page["effective_text"] == "Hợp đồng 1" and page["raw_text"] == raw
    same = c.put(
        f"/api/documents/{doc_id}/pages/1/correction", json={"corrected_text": "Hợp đồng 1", "base_version": 1}
    )
    assert same.status_code == 422
    assert db.scalar(select(AuditLog).where(AuditLog.action == "edit_ocr"))
    assert c.get(f"/api/documents/{doc_id}").json()["approval_status"] == "draft"
    assert (
        login("approver")
        .put(f"/api/documents/{doc_id}/pages/1/correction", json={"corrected_text": "x", "base_version": 1})
        .status_code
        == 403
    )


def test_search_accent_insensitive_grouped(seed, login, fake_engine, enqueued):
    doc_id = _processed(
        seed, login, enqueued, make_pdf(["Biên bản nghiệm thu công trình"], pages=3), "bb.pdf", title="Biên bản"
    )
    c = login("officer")
    for q in ("nghiệm thu", "NGHIEM THU"):
        res = c.get("/api/search", params={"q": q}).json()
        assert res["total"] == 1, q
        hit = res["items"][0]
        assert hit["document_id"] == doc_id and hit["category_name"] == "Hợp đồng"
        assert [p["page_number"] for p in hit["pages"]] == [1, 2, 3]
        p = hit["pages"][0]
        assert fold(p["snippet"][p["match_start"] : p["match_end"]]) == "nghiem thu"
    assert c.get("/api/search", params={"q": ""}).json()["items"] == []
    assert c.get("/api/search", params={"q": "khong-co-tu-nay"}).json()["total"] == 0


def test_search_scope_deleted_and_correction(seed, login, fake_engine, enqueued):
    doc_id = _processed(seed, login, enqueued, make_png(), "a.png")
    c = login("officer")
    assert c.get("/api/search", params={"q": "cong ty tnhh"}).json()["total"] == 1
    assert login("officerb").get("/api/search", params={"q": "cong ty tnhh"}).json()["total"] == 0
    c.put(
        f"/api/documents/{doc_id}/pages/1/correction", json={"corrected_text": "Công ty Cổ phần XYZ", "base_version": 0}
    )
    assert c.get("/api/search", params={"q": "cong ty tnhh"}).json()["total"] == 0
    assert c.get("/api/search", params={"q": "co phan xyz"}).json()["total"] == 1
    c.delete(f"/api/documents/{doc_id}")
    assert login("admin").get("/api/search", params={"q": "co phan xyz"}).json()["total"] == 0


def test_page_image_and_pages_list(seed, login, fake_engine, enqueued):
    doc_id = _processed(seed, login, enqueued, make_png(), "a.png")
    c = login("approver")
    assert c.get(f"/api/documents/{doc_id}/pages").json()[0]["ocr_status"] == "completed"
    img = c.get(f"/api/documents/{doc_id}/pages/1/image")
    assert img.status_code == 200 and img.content[:4] == b"\x89PNG"
    assert login("officerb").get(f"/api/documents/{doc_id}/pages/1/image").status_code == 403
    assert c.get(f"/api/documents/{doc_id}/pages/9").status_code == 404


def test_dashboard(seed, login, fake_engine, enqueued):
    stats = login("officer").get("/api/dashboard").json()
    assert stats["documents"] == 0 and stats["avg_confidence"] is None
    assert all(v == 0 for v in stats["extras"].values())  # số liệu P2 (nếu bật cờ) cũng là 0
    _processed(seed, login, enqueued, make_png(), "a.png")
    _processed(seed, login, enqueued, make_pdf(["abc"], pages=2), "b.pdf")
    stats = login("officer").get("/api/dashboard").json()
    assert stats["documents"] == 2 and stats["pages"] == 3 and stats["pages_ocr_done"] == 3
    assert stats["jobs_completed"] == 2 and stats["avg_confidence"] == 85.0
    assert {x["label"]: x["count"] for x in stats["by_job_status"]}["completed"] == 2
    assert stats["by_category"] == [{"label": "Hợp đồng", "count": 2}]
    assert login("officerb").get("/api/dashboard").json()["documents"] == 0
    assert login("admin").get("/api/dashboard").json()["documents"] == 2


def test_list_filters(seed, login, fake_engine, enqueued):
    c = login("officer")
    for i in range(3):
        upload(c, seed["category"].id, make_pdf([f"tai lieu {i}"]), f"t{i}.pdf", title=f"Tài liệu {i}")
    assert c.get("/api/documents", params={"status": "queued"}).json()["total"] == 3
    run_all_jobs(enqueued)
    assert c.get("/api/documents", params={"status": "completed"}).json()["total"] == 3
    page = c.get("/api/documents", params={"page_size": 2, "page": 2}).json()
    assert page["total"] == 3 and len(page["items"]) == 1
    assert c.get("/api/documents", params={"q": "liệu 1"}).json()["total"] == 1
