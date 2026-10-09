"""SearchIndex (port của search): cập nhật chỉ mục text hiệu lực của một trang.

Chỉ kết quả OCR mới nhất của trang mang search_vector; kết quả cũ để NULL, nên
"search_vector IS NOT NULL" = kết quả hiệu lực. Module ocr gọi index_page trong CÙNG
transaction khi lưu kết quả OCR hoặc bản chỉnh sửa (chỉ mục luôn nhất quán).
PostgreSQL: to_tsvector('simple', text đã chuẩn hóa) + GIN. SQLite (test): text đã chuẩn hóa.
"""

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.modules.search.domain.normalize import fold, nfc
from app.modules.search.infrastructure.tables import ocr_results
from app.shared.db import is_postgres


def index_page(db: Session, page_id: uuid.UUID, effective_text: str) -> None:
    db.flush()
    latest = db.scalar(
        select(ocr_results.c.id)
        .where(ocr_results.c.page_id == page_id)
        .order_by(ocr_results.c.created_at.desc())
        .limit(1)
    )
    if latest is None:
        return
    db.execute(
        update(ocr_results)
        .where(ocr_results.c.page_id == page_id, ocr_results.c.id != latest)
        .values(search_vector=None)
    )
    folded = fold(nfc(effective_text))
    value = func.to_tsvector("simple", folded) if is_postgres(db) else folded
    db.execute(update(ocr_results).where(ocr_results.c.id == latest).values(search_vector=value))
