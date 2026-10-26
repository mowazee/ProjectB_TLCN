"""SDD v0.8 FR-13 / D-09: chia sẻ tài liệu đã xuất bản.

Ma trận vai trò × chế độ chia sẻ × trạng thái xuất bản; mỗi ô kiểm CẢ policy Python (GET chi tiết) lẫn truy vấn SQL
dùng chung (danh sách, visible_document_ids) để hai bản không lệch nhau.
"""

from datetime import date, timedelta
from uuid import UUID

import pytest
from sqlalchemy import select

from app.modules.audit.infrastructure.models import AuditLog
from app.modules.users.application.manage import create_department, create_user
from tests.conftest import CTX, PASSWORD, make_pdf, upload

WF = "workflow,notifications,borrowing"
USERS = ["owner", "officer_a2", "approver", "viewer", "officer_b", "approver_b", "viewer_b", "officer_c", "admin"]


@pytest.fixture
def world(seed, db, login):
    """Phòng A: officer (chủ sở hữu), officer_a2, approver, viewer; phòng B: officerb, approver_b, viewer_b; phòng C."""
    dep_c = create_department(db, seed["admin_p"], code="C", name="Phòng C", ctx=CTX)

    def mk(username, role, dep):
        create_user(
            db,
            seed["admin_p"],
            username=username,
            email=f"{username}@test.vn",
            full_name=username.title(),
            password=PASSWORD,
            roles=[role],
            department_id=dep.id,
            ctx=CTX,
        )

    for username, role, dep in [
        ("officer_a2", "OFFICER", seed["dep_a"]),
        ("viewer", "VIEWER", seed["dep_a"]),
        ("approver_b", "APPROVER", seed["dep_b"]),
        ("viewer_b", "VIEWER", seed["dep_b"]),
        ("officer_c", "OFFICER", dep_c),
    ]:
        mk(username, role, dep)
    names = {"owner": "officer", "officer_b": "officerb"}
    clients = {u: login(names.get(u, u), features=WF) for u in USERS}
    ids = {u: UUID(c.get("/api/auth/me").json()["user"]["id"]) for u, c in clients.items()}
    doc_id = upload(clients["owner"], seed["category"].id, make_pdf(["Hop dong"]), "a.pdf", title="Hợp đồng A").json()[
        "document_id"
    ]
    return {"c": clients, "ids": ids, "doc": doc_id, "dep_b": seed["dep_b"].id, "dep_c": dep_c.id}


def _approve_publish(w):
    c, doc = w["c"], w["doc"]
    assert c["owner"].post(f"/api/documents/{doc}/approval/submit").status_code == 200
    assert c["approver"].post(f"/api/documents/{doc}/approval/approve").status_code == 200
    assert c["approver"].post(f"/api/documents/{doc}/approval/publish").status_code == 200


def _share(w, mode, departments=(), users=(), who="owner"):
    return w["c"][who].put(
        f"/api/documents/{w['doc']}/sharing",
        json={"share_mode": mode, "department_ids": list(departments), "user_ids": [str(w["ids"][u]) for u in users]},
    )


def _who_sees(w):
    """Người xem được tài liệu - kiểm policy (chi tiết) và SQL (danh sách) cho ra cùng kết quả."""
    seen = set()
    for user, client in w["c"].items():
        by_policy = client.get(f"/api/documents/{w['doc']}").status_code == 200
        listed = {d["id"] for d in client.get("/api/documents", params={"page_size": 100}).json()["items"]}
        assert by_policy == (w["doc"] in listed), f"policy và SQL lệch nhau với {user}"
        if by_policy:
            seen.add(user)
    return seen


A_DEPT = {"owner", "officer_a2", "approver", "admin"}


def test_visibility_matrix_policy_matches_sql(world):
    w = world
    # Chưa xuất bản: D-02 (phòng ban), VIEWER không thấy; cấu hình chia sẻ (nếu có) chưa có hiệu lực
    assert _who_sees(w) == A_DEPT
    _approve_publish(w)
    # Mặc định Nội bộ = đúng hành vi trước v0.8: cả phòng A, kể cả VIEWER
    assert _who_sees(w) == A_DEPT | {"viewer"}

    assert _share(w, "internal", departments=[w["dep_b"]]).status_code == 200
    assert _who_sees(w) == A_DEPT | {"viewer", "officer_b", "approver_b", "viewer_b"}

    # Riêng tư + một người: phòng A (trừ Kiểm duyệt viên của phòng) mất quyền; danh sách phòng ban bị bỏ
    r = _share(w, "private", departments=[w["dep_b"]], users=["viewer_b"])
    assert r.status_code == 200 and r.json()["departments"] == []
    assert _who_sees(w) == {"owner", "approver", "admin", "viewer_b"}

    assert _share(w, "public").status_code == 200
    assert _who_sees(w) == set(USERS)

    # Hủy xuất bản: chia sẻ tạm ngưng, giữ cấu hình; xuất bản lại thì áp dụng lại
    assert w["c"]["approver"].post(f"/api/documents/{w['doc']}/approval/unpublish").status_code == 200
    assert _who_sees(w) == A_DEPT
    assert w["c"]["owner"].get(f"/api/documents/{w['doc']}/sharing").json()["share_mode"] == "public"
    assert w["c"]["approver"].post(f"/api/documents/{w['doc']}/approval/publish").status_code == 200
    assert _who_sees(w) == set(USERS)


def test_sharing_only_grants_view_not_manage_or_review(world):
    w = world
    c, doc = w["c"], w["doc"]
    _approve_publish(w)
    _share(w, "internal", departments=[w["dep_b"]])
    detail = c["officer_b"].get(f"/api/documents/{doc}").json()
    assert detail["can_edit"] is False and detail["can_share"] is False
    assert c["officer_b"].patch(f"/api/documents/{doc}", json={"title": "x"}).status_code == 403
    assert c["officer_b"].delete(f"/api/documents/{doc}").status_code == 403
    assert (
        c["officer_b"]
        .put(f"/api/documents/{doc}/pages/1/correction", json={"corrected_text": "x", "base_version": 0})
        .status_code
        == 403
    )
    assert c["officer_b"].get(f"/api/documents/{doc}/file").status_code == 200  # D-08: tải được
    # Kiểm duyệt viên phòng B thấy tài liệu nhưng không hủy xuất bản được; nút cũng không hiện
    assert c["approver_b"].get(f"/api/documents/{doc}/approval").json()["allowed_actions"] == []
    assert c["approver_b"].post(f"/api/documents/{doc}/approval/unpublish").status_code == 403
    assert "unpublish" in c["approver"].get(f"/api/documents/{doc}/approval").json()["allowed_actions"]
    # Chủ sở hữu chia sẻ được; D-11: tài liệu đã xuất bản không ai sửa (kể cả chủ sở hữu) - hủy xuất bản trước
    assert detail["share_mode"] == "internal"
    assert c["owner"].get(f"/api/documents/{doc}").json()["can_share"] is True
    _share(w, "private")
    assert c["officer_a2"].patch(f"/api/documents/{doc}", json={"title": "x"}).status_code == 403
    assert c["owner"].patch(f"/api/documents/{doc}", json={"title": "Hợp đồng A1"}).status_code == 403


def test_sharing_api_rules(world, db):
    w = world
    c, doc = w["c"], w["doc"]
    early = _share(w, "public")
    assert early.status_code == 409 and early.json()["error"]["code"] == "DOCUMENT_NOT_PUBLISHED"
    _approve_publish(w)
    assert c["officer_a2"].get(f"/api/documents/{doc}/sharing").status_code == 403  # không phải chủ sở hữu
    assert _share(w, "public", who="officer_a2").status_code == 403
    assert _share(w, "public", who="approver_b").status_code == 403  # Kiểm duyệt viên phòng khác
    assert c["approver"].get(f"/api/documents/{doc}/sharing").status_code == 200  # v0.12: Kiểm duyệt viên phòng ban
    assert _share(w, "everyone").status_code == 422
    assert _share(w, "internal", departments=[9999]).status_code == 422
    c["admin"].patch(f"/api/users/{w['ids']['officer_c']}", json={"is_active": False})
    assert _share(w, "internal", users=["officer_c"]).status_code == 422  # người dùng đã khóa

    # Chủ sở hữu và phòng ban của tài liệu luôn có quyền: không lưu thành dòng chia sẻ
    r = _share(w, "internal", departments=[w["dep_b"], db_dep_a(w)], users=["owner", "viewer_b"]).json()
    assert [d["id"] for d in r["departments"]] == [w["dep_b"]]
    assert [u["username"] for u in r["users"]] == ["viewer_b"]
    assert r["owner_department"]["name"] == "Phòng A" and r["is_published"] is True
    assert _share(w, "public", who="admin").status_code == 200  # Admin quản lý chia sẻ mọi tài liệu

    logs = db.scalars(select(AuditLog).where(AuditLog.action == "update_sharing")).all()
    assert len(logs) == 2 and logs[0].state_before["share_mode"] == "internal"
    assert logs[0].state_after["department_ids"] == [w["dep_b"]]


def db_dep_a(w):
    return w["c"]["owner"].get("/api/auth/me").json()["user"]["department_id"]


def test_new_recipients_are_notified_once(world):
    w = world
    _approve_publish(w)
    _share(w, "private", users=["viewer_b"])
    _share(w, "private", users=["viewer_b", "officer_c"])  # viewer_b không nhận lại thông báo

    def shares(user):
        items = w["c"][user].get("/api/notifications").json()["items"]
        return [n for n in items if n["type"] == "share.added"]

    assert len(shares("viewer_b")) == 1 and len(shares("officer_c")) == 1
    note = shares("viewer_b")[0]
    assert note["link_url"] == f"/documents/{w['doc']}" and "Hợp đồng A" in note["message"]
    assert shares("owner") == []


def test_shared_with_me_filter(world):
    w = world
    _approve_publish(w)
    _share(w, "internal", departments=[w["dep_b"]])

    def shared(user):
        resp = w["c"][user].get("/api/documents", params={"shared": "with_me"})
        assert resp.status_code == 200
        return [d["id"] for d in resp.json()["items"]]

    assert shared("officer_b") == [w["doc"]] and shared("viewer_b") == [w["doc"]]
    assert shared("owner") == [] and shared("approver") == []  # của mình / phòng ban mình: không phải "được chia sẻ"
    assert shared("officer_c") == []
    assert w["c"]["owner"].get("/api/documents", params={"shared": "all"}).status_code == 422

    # Chia sẻ đích danh cho người CÙNG phòng ban (Riêng tư): vẫn là "được chia sẻ với tôi"
    _share(w, "private", users=["viewer", "officer_b"])
    assert shared("viewer") == [w["doc"]] and shared("officer_b") == [w["doc"]]
    assert shared("viewer_b") == [] and shared("approver") == []  # phòng B hết quyền; KDV phòng A chỉ thấy để duyệt
    # Toàn hệ thống: người phòng khác thấy ở đây, người cùng phòng không (tài liệu của phòng mình)
    _share(w, "public")
    assert shared("officer_c") == [w["doc"]] and shared("officer_a2") == []


def test_borrowing_by_shared_users_decided_by_document_department(world):
    w = world
    c, doc = w["c"], w["doc"]
    # D-11: gán vị trí lưu trữ là thao tác SỬA - chủ sở hữu làm khi tài liệu còn Nháp
    loc = c["admin"].post("/api/storage-locations", json={"name": "Kho 1", "code": "k1"}).json()
    assert (
        c["owner"].put(f"/api/documents/{doc}/storage-location", json={"storage_location_id": loc["id"]}).status_code
        == 200
    )
    _approve_publish(w)
    _share(w, "internal", departments=[w["dep_b"]])
    body = {
        "document_id": doc,
        "from_date": str(date.today() + timedelta(days=1)),
        "to_date": str(date.today() + timedelta(days=3)),
        "purpose": "Đối chiếu",
    }
    assert c["viewer_b"].post("/api/borrow-requests", json=body).status_code == 403  # FR-12: VIEWER không mượn
    req = c["officer_b"].post("/api/borrow-requests", json=body)
    assert req.status_code == 201, req.text
    req_id = req.json()["id"]
    # Kiểm duyệt viên phòng B không thấy trong danh sách cần duyệt, không duyệt được
    assert all(r["id"] != req_id for r in c["approver_b"].get("/api/borrow-requests").json()["items"])
    assert c["approver_b"].post(f"/api/borrow-requests/{req_id}/approve").status_code == 403
    assert any(r["id"] == req_id for r in c["approver"].get("/api/borrow-requests").json()["items"])
    assert c["approver"].post(f"/api/borrow-requests/{req_id}/approve").status_code == 200


def test_jobs_and_trash_stay_in_department_scope(world):
    w = world
    c, doc = w["c"], w["doc"]
    _approve_publish(w)
    _share(w, "public")
    assert c["officer_b"].get("/api/jobs").json()["total"] == 0  # job thuộc phòng ban quản lý tài liệu
    assert c["officer_a2"].get("/api/jobs").json()["total"] >= 1
    _share(w, "private")
    assert c["owner"].delete(f"/api/documents/{doc}").status_code == 403  # D-11: đã xuất bản - chỉ Admin xóa
    assert c["admin"].delete(f"/api/documents/{doc}").status_code == 204

    def trash(user):
        return [d["id"] for d in c[user].get("/api/documents", params={"lifecycle_status": "deleted"}).json()["items"]]

    assert trash("owner") == [doc] and trash("officer_a2") == []  # Riêng tư: chỉ chủ sở hữu khôi phục được
    assert c["officer_a2"].post(f"/api/documents/{doc}/restore").status_code == 403
    assert trash("officer_b") == []


def test_user_lookup(world):
    c = world["c"]
    found = c["owner"].get("/api/users/lookup", params={"q": "viewer"}).json()
    assert {u["username"] for u in found} == {"viewer", "viewer_b"}
    assert set(found[0]) == {"id", "username", "full_name", "department_name"}  # không lộ email, vai trò
    assert c["owner"].get("/api/users/lookup", params={"q": "officer"}).json()  # không có chính mình
    assert all(u["username"] != "officer" for u in c["owner"].get("/api/users/lookup", params={"q": "offic"}).json())
    assert c["owner"].get("/api/users/lookup", params={"q": "v"}).status_code == 422
    assert c["viewer"].get("/api/users/lookup", params={"q": "viewer"}).status_code == 403
    assert c["approver"].get("/api/users/lookup", params={"q": "viewer"}).status_code == 200  # v0.12: chia sẻ được
