"""SDD v0.7 FR-12, D-02 (bổ sung), D-08: vai trò Người dùng thông thường (VIEWER), tải file có audit, nhóm quyền."""

from sqlalchemy import select

from app.modules.audit.infrastructure.models import AuditLog
from app.modules.users.application.manage import create_user
from tests.conftest import CTX, PASSWORD, make_pdf, upload

WF = "workflow"


def _viewer(db, seed, username="viewer", dep="dep_a"):
    return create_user(
        db,
        seed["admin_p"],
        username=username,
        email=f"{username}@test.vn",
        full_name=username.title(),
        password=PASSWORD,
        roles=["VIEWER"],
        department_id=seed[dep].id,
        ctx=CTX,
    )


def _publish(officer, approver, doc_id):
    for c, action in ((officer, "submit"), (approver, "approve"), (approver, "publish")):
        assert c.post(f"/api/documents/{doc_id}/approval/{action}").status_code == 200, action


def test_viewer_sees_only_published_documents_of_own_department(seed, login, db):
    _viewer(db, seed)
    _viewer(db, seed, "viewerb", "dep_b")
    officer, approver = login("officer", features=WF), login("approver", features=WF)
    draft = upload(officer, seed["category"].id, make_pdf(["Bản nháp"]), "a.pdf", title="Nháp").json()["document_id"]
    pub = upload(officer, seed["category"].id, make_pdf(["Đã xuất bản"]), "b.pdf", title="Xuất bản").json()[
        "document_id"
    ]
    _publish(officer, approver, pub)

    viewer = login("viewer", features=WF)
    listed = viewer.get("/api/documents").json()
    assert [d["id"] for d in listed["items"]] == [pub]  # SQL (visible_document_ids) khớp policy
    assert viewer.get(f"/api/documents/{pub}").json()["can_edit"] is False
    assert viewer.get(f"/api/documents/{draft}").status_code == 403  # policy in_scope
    assert viewer.get(f"/api/documents/{pub}/pages").status_code == 200

    other_dep = login("viewerb", features=WF)
    assert other_dep.get("/api/documents").json()["total"] == 0
    assert other_dep.get(f"/api/documents/{pub}").status_code == 403

    # Hủy xuất bản -> VIEWER không còn thấy
    assert approver.post(f"/api/documents/{pub}/approval/unpublish").status_code == 200
    assert viewer.get(f"/api/documents/{pub}").status_code == 403


def test_viewer_without_workflow_sees_department_documents(seed, login, db):
    _viewer(db, seed)
    officer = login("officer", features="")
    doc_id = upload(officer, seed["category"].id, make_pdf(["a"]), "a.pdf").json()["document_id"]
    viewer = login("viewer", features="")
    assert viewer.get("/api/documents").json()["total"] == 1  # không có khái niệm xuất bản: cả phòng ban
    assert viewer.get(f"/api/documents/{doc_id}").status_code == 200


def test_viewer_is_read_only(seed, login, db):
    _viewer(db, seed)
    officer, approver = (
        login("officer", features="workflow,borrowing"),
        login("approver", features="workflow,borrowing"),
    )
    doc_id = upload(officer, seed["category"].id, make_pdf(["a"]), "a.pdf").json()["document_id"]
    _publish(officer, approver, doc_id)
    viewer = login("viewer", features="workflow,borrowing")
    assert upload(viewer, seed["category"].id, make_pdf(["a"]), "x.pdf").status_code == 403
    assert viewer.patch(f"/api/documents/{doc_id}", json={"title": "x"}).status_code == 403
    assert viewer.delete(f"/api/documents/{doc_id}").status_code == 403
    assert viewer.post(f"/api/documents/{doc_id}/approval/unpublish").status_code == 403
    borrow = viewer.post(
        "/api/borrow-requests", json={"document_id": doc_id, "from_date": "2099-01-01", "to_date": "2099-01-02"}
    )
    assert borrow.status_code == 403
    # Tài liệu đã xuất bản rồi bị xóa: không lọt vào thùng rác của người chỉ đọc. D-11: chỉ Admin xóa được tài liệu
    # đã xuất bản (chủ sở hữu chỉ xóa khi Nháp / Bị từ chối)
    assert officer.delete(f"/api/documents/{doc_id}").status_code == 403
    assert login("admin", features="workflow,borrowing").delete(f"/api/documents/{doc_id}").status_code == 204
    assert officer.get("/api/documents", params={"lifecycle_status": "deleted"}).json()["total"] == 1
    assert viewer.get("/api/documents", params={"lifecycle_status": "deleted"}).json()["total"] == 0


def test_download_any_role_in_scope_is_audited(seed, login, db):
    viewer = _viewer(db, seed)
    officer, approver = login("officer", features=WF), login("approver", features=WF)
    data = make_pdf(["noi dung"])
    doc_id = upload(officer, seed["category"].id, data, "a.pdf").json()["document_id"]
    _publish(officer, approver, doc_id)
    for c in (approver, login("viewer", features=WF)):
        r = c.get(f"/api/documents/{doc_id}/file")
        assert r.status_code == 200 and r.content == data
    assert login("officerb", features=WF).get(f"/api/documents/{doc_id}/file").status_code == 403
    db.rollback()
    who = db.scalars(select(AuditLog.user_id).where(AuditLog.action == "download_document")).all()
    assert sorted(map(str, who)) == sorted(map(str, [seed["approver"].id, viewer.id]))  # bị chặn thì không ghi


def test_roles_matrix_member_counts_and_user_filters(seed, login, db):
    _viewer(db, seed)
    admin = login("admin")
    roles = {r["name"]: r for r in admin.get("/api/roles").json()}
    assert list(roles) == ["ADMIN", "OFFICER", "APPROVER", "VIEWER"]
    assert roles["OFFICER"]["member_count"] == 2 and roles["VIEWER"]["member_count"] == 1
    assert all(r["permissions"] and r["summary"] for r in roles.values())
    assert login("officer").get("/api/roles").status_code == 403

    def names(**params):
        return sorted(u["username"] for u in admin.get("/api/users", params=params).json()["items"])

    assert names(role="VIEWER") == ["viewer"]
    assert names(role="OFFICER", department_id=seed["dep_b"].id) == ["officerb"]
    assert names(q="APPROVER@test") == ["approver"]  # tìm cả theo email
    officerb = seed["officer_b"]
    assert admin.patch(f"/api/users/{officerb.id}", json={"is_active": False}).status_code == 200
    assert "officerb" in names(is_active=False) and "officerb" not in names(is_active=True)
    assert admin.get("/api/users", params={"role": "KHONG-CO"}).status_code == 422


def test_assign_and_remove_role_membership(seed, login, db):
    admin = login("admin")
    approver = seed["approver"]
    r = admin.patch(f"/api/users/{approver.id}", json={"roles": ["APPROVER", "VIEWER"]})
    assert r.status_code == 200 and sorted(r.json()["roles"]) == ["APPROVER", "VIEWER"]
    assert {x["name"]: x["member_count"] for x in admin.get("/api/roles").json()}["VIEWER"] == 1
    assert admin.patch(f"/api/users/{approver.id}", json={"roles": []}).status_code == 422  # cần ít nhất một vai trò
    me = seed["admin"]
    assert admin.patch(f"/api/users/{me.id}", json={"roles": ["OFFICER"]}).status_code == 422  # tự gỡ Admin
