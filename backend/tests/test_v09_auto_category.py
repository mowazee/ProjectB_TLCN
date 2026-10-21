"""D-10 (SDD v0.9): tải lên với Danh mục gợi ý - tài liệu vào "Chưa phân loại", job CLASSIFY tự áp dụng sau OCR."""

import uuid

from sqlalchemy import select

from app.modules.audit.infrastructure.models import AuditLog
from app.modules.categories.domain.system import UNCLASSIFIED_CODE
from app.modules.categories.infrastructure.models import Category
from app.modules.documents.infrastructure.models import Document
from app.modules.jobs.infrastructure.models import ProcessingJob
from app.modules.notifications.infrastructure.models import Notification
from app.shared.config import settings
from tests.conftest import make_png, run_all_jobs, upload
from tests.test_p2_extraction_classification import CONG_VAN, HOP_DONG, _lines

FEATURES = "classification,notifications"


def _auto_upload(client, data=None, name="auto.png", **extra):
    form = {"category_mode": "auto", **{k: str(v) for k, v in extra.items()}}
    return client.post(
        "/api/documents", data=form, files={"file": (name, data or make_png(), "application/octet-stream")}
    )


def _train(client, fake_engine, enqueued, seed):
    """Hai mẫu do người dùng chọn danh mục: Hợp đồng và Công văn."""
    fake_engine.lines = _lines(HOP_DONG)
    upload(client, seed["category"].id, make_png(), "hd1.png")
    run_all_jobs(enqueued)
    fake_engine.lines = _lines(CONG_VAN)
    upload(client, seed["category2"].id, make_png(), "cv1.png")
    run_all_jobs(enqueued)


def _notifications(db, type_):
    db.rollback()
    return db.scalars(select(Notification).where(Notification.type == type_)).all()


def test_upload_auto_mode_goes_to_unclassified(seed, login, db, fake_engine, enqueued):
    c = login("officer", features=FEATURES)
    r = _auto_upload(c)
    assert r.status_code == 201, r.text
    doc = c.get(f"/api/documents/{r.json()['document_id']}").json()
    assert doc["category"]["name"] == "Chưa phân loại" and doc["category_source"] == "pending"
    db.rollback()
    log = db.scalar(select(AuditLog).where(AuditLog.action == "upload_document"))
    assert log.state_after["category_source"] == "pending"
    # danh mục hệ thống chỉ có một, dùng lại cho lần tải sau
    assert _auto_upload(c, name="auto2.png").status_code == 201
    assert len(db.scalars(select(Category).where(Category.code == UNCLASSIFIED_CODE)).all()) == 1

    cats = {x["code"]: x for x in c.get("/api/categories").json()}
    assert cats[UNCLASSIFIED_CODE]["is_system"] is True and cats["HOP-DONG"]["is_system"] is False


def test_upload_mode_validation(seed, login, db, fake_engine, enqueued):
    off = login("officer", features="")
    r = _auto_upload(off)
    assert r.status_code == 422 and r.json()["error"]["code"] == "CATEGORY_MODE_UNAVAILABLE"

    c = login("officer", features=FEATURES)
    r = c.post("/api/documents", data={}, files={"file": ("x.png", make_png(), "application/octet-stream")})
    assert r.status_code == 422 and r.json()["error"]["code"] == "CATEGORY_REQUIRED"  # mặc định user: bắt buộc chọn
    assert (
        c.post("/api/documents", data={"category_mode": "xyz"}, files={"file": ("x.png", make_png())}).status_code
        == 422
    )

    sys_id = c.get(f"/api/documents/{_auto_upload(c).json()['document_id']}").json()["category"]["id"]
    r = upload(c, sys_id, make_png(), "chon-he-thong.png")
    assert r.status_code == 422 and r.json()["error"]["code"] == "CATEGORY_SYSTEM"  # không tự chọn "Chưa phân loại"
    ok = upload(c, seed["category"].id, make_png(), "user.png").json()
    assert c.get(f"/api/documents/{ok['document_id']}").json()["category_source"] == "user"


def test_system_category_is_protected(seed, login, db, fake_engine, enqueued):
    c = login("officer", features=FEATURES)
    sys_id = c.get(f"/api/documents/{_auto_upload(c).json()['document_id']}").json()["category"]["id"]
    admin = login("admin", features=FEATURES)
    r = admin.patch(f"/api/categories/{sys_id}", json={"is_active": False})
    assert r.status_code == 409 and r.json()["error"]["code"] == "CATEGORY_SYSTEM"
    r = admin.patch(f"/api/categories/{sys_id}", json={"parent_id": seed["category"].id})
    assert r.status_code == 409 and r.json()["error"]["code"] == "CATEGORY_SYSTEM"


def test_auto_classify_applies_top_suggestion(seed, login, db, fake_engine, enqueued):
    c = login("officer", features=FEATURES)
    _train(c, fake_engine, enqueued, seed)
    fake_engine.lines = _lines(HOP_DONG[:1] + HOP_DONG[2:])
    doc_id = _auto_upload(c).json()["document_id"]
    run_all_jobs(enqueued)

    doc = c.get(f"/api/documents/{doc_id}").json()
    assert doc["category"]["id"] == seed["category"].id and doc["category_source"] == "auto"
    sugg = c.get(f"/api/documents/{doc_id}/category-suggestions").json()["items"]
    assert sugg[0]["category_id"] == seed["category"].id and sugg[0]["is_current"] is True
    db.rollback()
    log = db.scalar(select(AuditLog).where(AuditLog.action == "auto_classify"))
    assert log.user_id is None and log.state_before["category_source"] == "pending"
    assert log.state_after["category_id"] == seed["category"].id and log.state_after["score"] == sugg[0]["score"]
    job = db.scalar(
        select(ProcessingJob).where(ProcessingJob.kind == "CLASSIFY", ProcessingJob.document_id == uuid.UUID(doc_id))
    )
    assert job.result["auto_applied"] == seed["category"].id
    (note,) = _notifications(db, "classify.auto")
    assert note.user_id == seed["officer"].id and "Hợp đồng" in note.message and note.link_url == f"/documents/{doc_id}"

    # chấp nhận gợi ý khác: danh mục chuyển sang do người dùng xác nhận
    r = c.post(f"/api/documents/{doc_id}/category-suggestions/accept", json={"category_id": seed["category2"].id})
    assert r.status_code == 200
    doc = c.get(f"/api/documents/{doc_id}").json()
    assert doc["category"]["id"] == seed["category2"].id and doc["category_source"] == "user"
    current = [
        s["category_id"]
        for s in c.get(f"/api/documents/{doc_id}/category-suggestions").json()["items"]
        if s["is_current"]
    ]
    assert current == [seed["category2"].id]  # tại một thời điểm chỉ một danh mục đang áp dụng


def test_below_threshold_stays_unclassified_and_notifies(seed, login, db, fake_engine, enqueued, monkeypatch):
    c = login("officer", features=FEATURES)
    _train(c, fake_engine, enqueued, seed)
    monkeypatch.setattr(settings, "CLASSIFY_MIN_SCORE", 0.99)
    doc_id = _auto_upload(c).json()["document_id"]
    upload(c, seed["category"].id, make_png(), "user.png")  # người dùng tự chọn: không báo dù dưới ngưỡng
    run_all_jobs(enqueued)
    doc = c.get(f"/api/documents/{doc_id}").json()
    assert doc["category"]["name"] == "Chưa phân loại" and doc["category_source"] == "pending"
    (note,) = _notifications(db, "classify.unsure")
    assert note.user_id == seed["officer"].id
    assert _notifications(db, "classify.auto") == []

    # người dùng tự chọn: thoát trạng thái chờ
    r = c.patch(f"/api/documents/{doc_id}", json={"category_id": seed["category2"].id})
    assert r.status_code == 200, r.text
    assert c.get(f"/api/documents/{doc_id}").json()["category_source"] == "user"


def test_auto_classify_never_overrides_user_or_previous_auto(seed, login, db, fake_engine, enqueued):
    from types import SimpleNamespace

    from app.modules.classification.application.suggest import enqueue_classification

    c = login("officer", features=FEATURES)
    _train(c, fake_engine, enqueued, seed)
    fake_engine.lines = _lines(HOP_DONG[:1] + HOP_DONG[2:])
    user_doc = upload(c, seed["category2"].id, make_png(), "nham.png").json()["document_id"]  # người dùng chọn nhầm
    run_all_jobs(enqueued)
    assert c.get(f"/api/documents/{user_doc}").json()["category"]["id"] == seed["category2"].id

    auto_doc = _auto_upload(c).json()["document_id"]
    run_all_jobs(enqueued)
    db.rollback()
    db.get(Document, uuid.UUID(auto_doc)).category_id = seed["category2"].id  # giả lập: lần chạy sau gợi ý khác
    db.commit()
    enqueue_classification(SimpleNamespace(document_id=uuid.UUID(auto_doc)))  # OCR chạy lại -> CLASSIFY lại
    run_all_jobs(enqueued)
    assert (
        c.get(f"/api/documents/{auto_doc}").json()["category"]["id"] == seed["category2"].id
    )  # đã auto: không đổi nữa
    db.rollback()
    assert len(db.scalars(select(AuditLog).where(AuditLog.action == "auto_classify")).all()) == 1

    from app.modules.documents.application.manage import apply_auto_category

    for doc_id in (user_doc, auto_doc):  # use case lõi cũng chỉ nhận tài liệu đang chờ
        assert apply_auto_category(db, uuid.UUID(doc_id), seed["category"].id) is False
    db.rollback()


def test_training_uses_only_user_confirmed_labels(seed, login, db, fake_engine, enqueued, monkeypatch):
    from app.modules.classification.application import suggest

    c = login("officer", features=FEATURES)
    _train(c, fake_engine, enqueued, seed)
    fake_engine.lines = _lines(HOP_DONG)
    _auto_upload(c, name="auto-hd.png")  # sẽ thành auto
    run_all_jobs(enqueued)
    monkeypatch.setattr(settings, "CLASSIFY_MIN_SCORE", 0.99)
    _auto_upload(c, name="cho.png")  # dưới ngưỡng: pending
    run_all_jobs(enqueued)

    seen: list = []
    real_train = suggest.sklearn_classifier.train
    monkeypatch.setattr(
        suggest.sklearn_classifier, "train", lambda samples: seen.append(samples) or real_train(samples)
    )
    monkeypatch.setattr(settings, "CLASSIFY_MIN_SCORE", 0.0)
    upload(c, seed["category"].id, make_png(), "moi.png")
    run_all_jobs(enqueued)
    (samples,) = seen
    db.rollback()
    sys_id = db.scalar(select(Category.id).where(Category.code == UNCLASSIFIED_CODE))
    labels = [cid for cid, _ in samples]
    # 2 mẫu khởi đầu từ tên danh mục + 2 tài liệu người dùng chọn; không có tài liệu auto/pending
    assert sorted(labels) == sorted([seed["category"].id, seed["category2"].id] * 2)
    assert sys_id not in labels
    sugg = c.get(f"/api/documents/{_auto_upload(c).json()['document_id']}/category-suggestions").json()["items"]
    assert sys_id not in [s["category_id"] for s in sugg]
