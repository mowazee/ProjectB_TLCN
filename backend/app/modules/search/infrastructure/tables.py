"""Phép chiếu chỉ đọc/ghi các cột search cần (không import model của module ocr/documents, R5).

search sở hữu ngữ nghĩa cột ocr_results.search_vector (chỉ mục trên text hiệu lực).
"""

from sqlalchemy import Integer, Text, Uuid, column, table
from sqlalchemy.types import DateTime

from app.shared.db import SearchVectorType

ocr_results = table(
    "ocr_results",
    column("id", Uuid),
    column("page_id", Uuid),
    column("raw_text", Text),
    column("search_vector", SearchVectorType),
    column("created_at", DateTime(timezone=True)),
)

ocr_corrections = table(
    "ocr_corrections",
    column("page_id", Uuid),
    column("version", Integer),
    column("corrected_text", Text),
)

document_pages = table(
    "document_pages",
    column("id", Uuid),
    column("document_id", Uuid),
    column("page_number", Integer),
)
