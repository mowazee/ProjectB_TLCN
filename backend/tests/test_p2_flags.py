"""NFR-09: cờ tính năng - tắt thì endpoint P2 trả 404; bật toàn bộ thì luồng MVP vẫn chạy."""

import pytest

from tests.conftest import P2_ALL, make_png, run_all_jobs, upload

P2_ENDPOINTS = [
    ("get", "/api/reviews"),
    ("get", "/api/notifications"),
    ("get", "/api/borrow-requests"),
    ("get", "/api/storage-locations"),
    ("get", "/api/imports/00000000-0000-0000-0000-000000000000"),
    ("get", "/api/audit/1/rollback"),
    ("get", "/api/documents/00000000-0000-0000-0000-000000000000/fields"),
    ("get", "/api/documents/00000000-0000-0000-0000-000000000000/category-suggestions"),
    ("get", "/api/documents/00000000-0000-0000-0000-000000000000/pages/1/versions"),
    ("get", "/api/documents/00000000-0000-0000-0000-000000000000/pages/1/highlights"),
    ("post", "/api/documents/00000000-0000-0000-0000-000000000000/reprocess"),
]


@pytest.mark.parametrize(("method", "path"), P2_ENDPOINTS)
def test_p2_endpoints_404_when_flags_off(seed, login, method, path):
    c = login("admin", features="")
    assert getattr(c, method)(path).status_code == 404


def test_me_lists_enabled_features(seed, login):
    c = login("officer", features="workflow,highlight")
    assert sorted(c.get("/api/auth/me").json()["features"]) == ["highlight", "workflow"]


def test_mvp_flow_with_all_flags(seed, login, fake_engine, enqueued):
    c = login("officer", features=P2_ALL)
    doc_id = upload(c, seed["category"].id, make_png(), "a.png").json()["document_id"]
    outcomes = run_all_jobs(enqueued)  # OCR + EXTRACT + CLASSIFY
    assert [o.value for o in outcomes] == ["completed"] * 3
    assert c.get("/api/search", params={"q": "cong ty"}).json()["total"] == 1
    stats = c.get("/api/dashboard").json()
    assert stats["jobs_completed"] == 1 and stats["documents"] == 1  # chỉ đếm job OCR
    assert set(stats["extras"]) == {"documents_pending_review", "borrow_pending", "borrow_overdue"}
    page = c.get(f"/api/documents/{doc_id}/pages/1").json()
    assert page["version"] == 0
