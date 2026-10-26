"""D-11 (SDD v0.12): quyền sửa theo chủ sở hữu và trạng thái duyệt; P2-01 thêm withdraw, return."""

import uuid

import pytest
from sqlalchemy import select

from app.modules.audit.infrastructure.models import AuditLog
from app.modules.documents.domain import policies as P
from app.modules.jobs.infrastructure.models import ProcessingJob
from app.modules.users.application.manage import create_user
from app.shared.context import Principal
from tests.conftest import CTX, PASSWORD, make_pdf, run_all_jobs, upload

F = "workflow,notifications,extraction,classification,rollback,handwriting"
OWNER_ID, DEP_A, DEP_B = uuid.uuid4(), 1, 2


def _p(roles: set[str], dep: int | None = DEP_A, uid: uuid.UUID | None = None) -> Principal:
    return Principal(uid or uuid.uuid4(), "u", "U", dep, frozenset(roles))


PEOPLE = {
    "owner": _p({"OFFICER"}, uid=OWNER_ID),
    "colleague": _p({"OFFICER"}),
    "approver_a": _p({"APPROVER"}),
    "approver_b": _p({"APPROVER"}, dep=DEP_B),
    "admin": _p({"ADMIN"}, dep=None),
    "viewer": _p({"VIEWER"}),
}
STATES = ["draft", "rejected", "pending_review", "approved", "published", "unpublished"]
OWNER_PHASE, REVIEW_PHASE = {"draft", "rejected"}, {"pending_review", "approved", "unpublished"}
# Bảng D-11 của SDD v0.12: quyền -> {người: tập trạng thái được phép}
EXPECTED = {
    P.EDIT: {"owner": OWNER_PHASE, "approver_a": REVIEW_PHASE, "admin": REVIEW_PHASE},
    P.REPROCESS: {"owner": OWNER_PHASE},
    P.DELETE: {"owner": OWNER_PHASE, "admin": set(STATES)},
    P.RESTORE: {"owner": set(STATES), "admin": set(STATES)},
    P.CANCEL_JOB: {"owner": OWNER_PHASE, "admin": set(STATES)},
    P.SUBMIT: {"owner": OWNER_PHASE},
    P.WITHDRAW: {"owner": {"pending_review", "approved"}},
    P.SHARE: {"owner": {"published"}, "approver_a": {"published"}, "admin": {"published"}},
}


def _scope(state: str, *, workflow: bool = True, owner: uuid.UUID = OWNER_ID) -> P.DocScope:
    return P.DocScope(owner, DEP_A, state, workflow, "public")  # Toàn hệ thống: ai cũng xem được tài liệu đã xuất bản


@pytest.mark.parametrize("permission", list(EXPECTED))
@pytest.mark.parametrize("who", list(PEOPLE))
@pytest.mark.parametrize("state", STATES)
def test_d11_matrix(permission, who, state):
    expected = state in EXPECTED[permission].get(who, set())
    assert P.allowed(PEOPLE[who], _scope(state), permission) is expected


def test_workflow_off_only_owner_edits():
    for who, p in PEOPLE.items():
        assert P.can_edit(p, _scope("draft", workflow=False)) is (who == "owner")
        assert P.can_reprocess(p, _scope("draft", workflow=False)) is (who == "owner")
        assert not P.can_submit(p, _scope("draft", workflow=False))


def test_admin_owner_reprocesses_own_document_and_lock_reasons():
    admin = PEOPLE["admin"]
    assert P.can_reprocess(admin, _scope("draft", owner=admin.id))
    assert not P.can_reprocess(admin, _scope("draft"))
    owner, colleague = PEOPLE["owner"], PEOPLE["colleague"]
    assert P.edit_lock_reason(owner, _scope("draft")) is None
    assert "Rút lại" in P.edit_lock_reason(owner, _scope("pending_review"))
    assert "trả lại" in P.edit_lock_reason(owner, _scope("unpublished"))
    assert "hủy xuất bản" in P.edit_lock_reason(PEOPLE["approver_a"], _scope("published"))
    # Người không bao giờ sửa được (đồng nghiệp, người được chia sẻ, người chỉ đọc): không hiện nút mờ, nhưng API vẫn
    # trả lý do cụ thể khi bị từ chối
    assert P.edit_lock_reason(colleague, _scope("draft")) is None
    assert P.edit_lock_reason(PEOPLE["approver_b"], _scope("pending_review")) is None
    assert P.edit_lock_reason(PEOPLE["viewer"], _scope("published")) is None
    assert "người tải lên" in P.denial_message(colleague, _scope("draft"), P.EDIT)
    assert "Không chạy lại OCR" in P.denial_message(PEOPLE["approver_a"], _scope("pending_review"), P.REPROCESS)


# ---------------------------------------------------------------- API end to end
@pytest.fixture
def people(seed, db):
    def mk(username, role, dep):
        return create_user(
            db,
            seed["admin_p"],
            username=username,
            email=f"{username}@test.vn",
            full_name=username.title(),
            password=PASSWORD,
            roles=[role],
            department_id=dep,
            ctx=CTX,
        )

    mk("colleague", "OFFICER", seed["dep_a"].id)
    mk("approverb", "APPROVER", seed["dep_b"].id)
    return seed


def _ocr_page(client, doc_id):
    page = client.get(f"/api/documents/{doc_id}/pages/1").json()
    return {"corrected_text": page["effective_text"] + " sửa", "base_version": page["version"]}


def _act(client, doc_id, action, **body):
    return client.post(f"/api/documents/{doc_id}/approval/{action}", json=body or None)


def test_d11_lifecycle_api(people, login, db, fake_engine, enqueued):
    owner = login("officer", features=F)
    colleague, approver = login("colleague", features=F), login("approver", features=F)
    approver_b, admin = login("approverb", features=F), login("admin", features=F)
    doc_id = upload(owner, people["category"].id, make_pdf(["Quyet dinh so 1"]), "qd.pdf").json()["document_id"]
    run_all_jobs(enqueued)
    base = f"/api/documents/{doc_id}"
    cat2 = {"category_id": people["category2"].id}

    def perms(client):
        return set(client.get(base).json()["permissions"])

    # Nháp: chỉ chủ sở hữu sửa, chạy lại OCR, xóa; đồng nghiệp cùng phòng, kiểm duyệt viên, Admin chỉ xem
    assert perms(owner) == {"edit", "reprocess", "delete", "restore", "cancel_job", "submit"}
    assert perms(colleague) == set() and colleague.get(base).json()["edit_lock_reason"] is None  # không hiện nút
    for c in (colleague, approver, admin):
        assert c.patch(base, json=cat2).status_code == 403
        assert c.put(f"{base}/pages/1/correction", json=_ocr_page(c, doc_id)).status_code == 403
        assert c.post(f"{base}/reprocess", json={"ocr_profile": "print"}).status_code == 403
    r = colleague.patch(base, json=cat2)
    assert "người tải lên" in r.json()["error"]["message"]
    assert colleague.delete(base).status_code == 403
    assert owner.patch(base, json={"title": "Quyết định số 1"}).status_code == 200

    # Chờ duyệt: chủ sở hữu khóa (Rút lại); kiểm duyệt viên phòng ban sửa nhưng không chạy lại OCR
    assert colleague.post(f"{base}/approval/submit").status_code == 403  # chỉ chủ sở hữu gửi duyệt
    assert _act(owner, doc_id, "submit").status_code == 200
    assert owner.get(f"{base}/approval").json()["allowed_actions"] == ["withdraw"]
    assert owner.patch(base, json=cat2).status_code == 403 and perms(owner) == {"restore", "withdraw"}
    assert owner.delete(base).status_code == 403
    assert approver.patch(base, json=cat2).status_code == 200
    assert approver.put(f"{base}/pages/1/correction", json=_ocr_page(approver, doc_id)).status_code == 200
    r = approver.post(f"{base}/reprocess", json={"ocr_profile": "print"})
    assert r.status_code == 403 and "Không chạy lại OCR" in r.json()["error"]["message"]
    assert approver_b.patch(base, json=cat2).status_code in (403, 404)  # phòng khác
    ocr_job = owner.get(base).json()["job_id"]
    assert (
        approver.post(f"/api/jobs/{ocr_job}/retry").status_code == 403
    )  # chạy lại job OCR = chạy lại OCR, không phải SỬA
    assert admin.patch(base, json={"title": "Admin sửa khi duyệt"}).status_code == 200
    assert approver.get(f"{base}/approval").json()["allowed_actions"] == ["approve", "reject"]

    # Rút lại -> Nháp: chủ sở hữu sửa, chạy lại OCR được
    assert _act(approver, doc_id, "withdraw").status_code == 403
    assert _act(owner, doc_id, "withdraw").json()["approval_status"] == "draft"
    assert owner.post(f"{base}/reprocess", json={"ocr_profile": "print"}).status_code == 202
    run_all_jobs(enqueued)

    # Duyệt, xuất bản: không ai sửa; chia sẻ: chủ sở hữu, kiểm duyệt viên phòng ban, Admin
    for step, who in (("submit", owner), ("approve", approver), ("publish", approver)):
        assert _act(who, doc_id, step).status_code == 200
    for c in (owner, approver, admin):
        assert c.patch(base, json=cat2).status_code == 403
    assert approver.patch(base, json=cat2).json()["error"]["message"].startswith("Tài liệu đã xuất bản")
    sharing = {"share_mode": "internal", "department_ids": [], "user_ids": []}
    for c in (owner, approver, admin):
        assert c.put(f"{base}/sharing", json=sharing).status_code == 200
    assert colleague.put(f"{base}/sharing", json=sharing).status_code == 403
    assert "share" in perms(approver) and "share" not in perms(colleague)

    # Hủy xuất bản: kiểm duyệt viên sửa; Trả lại cần ghi chú; về Nháp cho chủ sở hữu
    assert _act(approver, doc_id, "unpublish").status_code == 200
    assert owner.patch(base, json=cat2).status_code == 403
    assert approver.patch(base, json={"title": "Sửa sau hủy xuất bản"}).status_code == 200
    assert _act(approver, doc_id, "return").status_code == 422
    r = _act(approver, doc_id, "return", comments="Bổ sung số hiệu")
    assert r.status_code == 200 and r.json()["approval_status"] == "draft"
    assert owner.patch(base, json={"document_code": "01/QĐ"}).status_code == 200
    bell = owner.get("/api/notifications").json()["items"]
    assert any(n["type"] == "approval.return" and "Bổ sung số hiệu" in n["message"] for n in bell)
    history = [h["action"] for h in owner.get(f"{base}/approvals").json()]
    assert history[-1] == "return" and "withdraw" in history

    # Admin xóa được ở mọi trạng thái; khôi phục: chủ sở hữu, Admin
    assert colleague.post(f"{base}/restore").status_code in (403, 404)
    assert admin.delete(base).status_code == 204
    assert owner.post(f"{base}/restore").status_code == 200


def test_rollback_bypasses_d11_and_job_retry_follows_reprocess(people, login, db, fake_engine, enqueued):
    owner, colleague = login("officer", features=F), login("colleague", features=F)
    approver, admin = login("approver", features=F), login("admin", features=F)
    doc_id = upload(owner, people["category"].id, make_pdf(["Hop dong"]), "hd.pdf").json()["document_id"]
    run_all_jobs(enqueued)
    base = f"/api/documents/{doc_id}"
    assert owner.patch(base, json={"title": "Tên mới"}).status_code == 200
    for step, who in (("submit", owner), ("approve", approver), ("publish", approver)):
        assert _act(who, doc_id, step).status_code == 200
    db.rollback()
    log = db.scalar(select(AuditLog).where(AuditLog.action == "update_document"))
    r = admin.post(f"/api/audit/{log.id}/rollback", json={"confirm": False})
    assert r.status_code == 200, r.text  # tài liệu đã xuất bản: rollback vẫn làm được (P2-09)
    assert owner.get(base).json()["title"] != "Tên mới"

    # Chạy lại job OCR lỗi = chạy lại OCR (D-11); dừng job: chủ sở hữu hoặc Admin
    doc2 = upload(owner, people["category"].id, make_pdf(["Cong van"]), "cv.pdf").json()["document_id"]
    job_id = owner.get(f"/api/documents/{doc2}").json()["job_id"]
    assert colleague.post(f"/api/jobs/{job_id}/cancel").status_code == 403
    assert admin.post(f"/api/jobs/{job_id}/cancel").status_code == 200  # Admin dừng job kẹt
    assert admin.post(f"/api/jobs/{job_id}/retry").status_code == 403  # nhưng không chạy lại OCR của người khác
    assert colleague.post(f"/api/jobs/{job_id}/retry").status_code == 403
    assert owner.post(f"/api/jobs/{job_id}/retry").status_code == 200
    db.rollback()
    assert db.get(ProcessingJob, uuid.UUID(job_id)).status == "queued"
