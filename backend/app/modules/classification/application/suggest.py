"""UC-22 Phân loại tự động (P2-05).

Sau OcrCompleted: job CLASSIFY huấn luyện nhanh scikit-learn TF-IDF + Logistic Regression trên tài liệu đã có
danh mục (cộng tên/mô tả danh mục làm mẫu khởi đầu), đề xuất tối đa 3 danh mục đang dùng kèm xác suất, lưu ở
processing_jobs.result. Không tự ghi đè danh mục; chỉ cập nhật category_id khi người dùng chấp nhận
(qua use case update_document của lõi, có audit).
"""

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.modules.categories.application import manage as categories
from app.modules.classification.domain.ports import TextClassifier
from app.modules.classification.infrastructure import sklearn_classifier
from app.modules.documents.application import manage as doc_manage
from app.modules.documents.application import queries as documents
from app.modules.jobs.application import queries as jobs
from app.modules.jobs.application.create import create_job
from app.modules.jobs.domain.model import JobError
from app.modules.ocr.application.queries import document_effective_text
from app.shared.config import settings
from app.shared.context import Principal, RequestContext
from app.shared.db import SessionLocal
from app.shared.errors import ConflictError, UnprocessableError

KIND = "CLASSIFY"
TOP_K = 3
_SYSTEM = Principal(uuid.UUID(int=0), "system", "System", None, frozenset({"ADMIN"}))


@dataclass
class Suggestion:
    category_id: int
    name: str
    score: float
    is_current: bool


def _doc_text(db: Session, document_id: uuid.UUID) -> str:
    return document_effective_text(db, [p.id for p in documents.list_pages(db, document_id)])


def enqueue_classification(evt: Any) -> None:
    with SessionLocal() as db:
        try:
            create_job(db, kind=KIND, document_id=evt.document_id, queue="default")
            db.commit()
        except ConflictError:
            db.rollback()


def run_classification(ctx: Any) -> None:
    db: Session = ctx.db
    doc = documents.get_document(db, ctx.document_id)
    if doc is None or not documents.is_active(db, ctx.document_id):
        raise JobError("DOCUMENT_DELETED", "Tài liệu đã bị xóa")
    active = {c.id: c for c in categories.active_categories(db)}
    samples: list[tuple[int, str]] = [(c.id, f"{c.name} {c.description or ''}") for c in active.values()]
    ids_stmt = documents.visible_document_ids(_SYSTEM).limit(settings.CLASSIFY_MAX_TRAINING_DOCS)
    other_ids = [i for i in db.scalars(ids_stmt).all() if i != doc.id]
    briefs = documents.document_brief(db, set(other_ids))
    for doc_id in other_ids:
        cat = briefs.get(doc_id, {}).get("category_id")
        if cat in active:
            text = _doc_text(db, doc_id)
            if text.strip():
                samples.append((cat, text))
    model: TextClassifier = sklearn_classifier.train(samples)
    scores = model.predict(_doc_text(db, doc.id), top_k=TOP_K)
    # UC-22 2a: điểm CAO NHẤT dưới ngưỡng → không gợi ý gì; ngược lại trả đủ tối đa 3 gợi ý
    if not scores or scores[0][1] < settings.CLASSIFY_MIN_SCORE:
        scores = []
    suggestions = [{"category_id": cid, "name": active[cid].name, "score": round(score, 4)} for cid, score in scores]
    ctx.set_result(
        {
            "model": model.name,
            "training_docs": model.n_docs,
            "category_id_at_run": doc.category_id,
            "suggestions": suggestions,
        }
    )


def get_suggestions(db: Session, principal: Principal, document_id: uuid.UUID) -> tuple[list[Suggestion], Any]:
    doc = documents.ensure_can_view(db, principal, document_id)
    result = jobs.latest_completed_result(db, doc.id, KIND) or {}
    active = {c.id: c for c in categories.active_categories(db)}  # chỉ gợi ý danh mục đang dùng
    out = []
    for s in result.get("suggestions", [])[:TOP_K]:
        cid = int(s["category_id"])
        if cid in active:
            out.append(Suggestion(cid, active[cid].name, float(s["score"]), cid == doc.category_id))
    return out, jobs.latest_job(db, doc.id, KIND)


def accept(
    db: Session, principal: Principal, document_id: uuid.UUID, category_id: int, ctx: RequestContext
) -> Suggestion:
    suggestions, job = get_suggestions(db, principal, document_id)
    chosen = next((s for s in suggestions if s.category_id == category_id), None)
    if chosen is None:
        raise UnprocessableError("Danh mục không nằm trong gợi ý hiện có", fields={"category_id": "not_suggested"})
    if chosen.is_current:
        raise UnprocessableError("Tài liệu đã thuộc danh mục này", code="NO_CHANGES")
    doc_manage.update_document(
        db,
        principal,
        document_id,
        {"category_id": category_id},
        ctx,
        action="accept_category_suggestion",
        extra_after={
            "score": chosen.score,
            "job_id": str(job.id) if job else None,
            "model": (job.result or {}).get("model") if job else None,  # model đã sinh gợi ý này
        },
    )
    chosen.is_current = True
    return chosen
