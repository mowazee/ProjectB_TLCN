"""Event của ocr: P2-04/P2-05 subscribe OcrCompleted; P3 re-embed sau CorrectionSaved."""

import uuid
from dataclasses import dataclass

from app.shared.domain_events import Event


@dataclass(frozen=True)
class OcrCompleted(Event):
    document_id: uuid.UUID
    job_id: uuid.UUID


@dataclass(frozen=True)
class CorrectionSaved(Event):
    document_id: uuid.UUID
    page_id: uuid.UUID
    page_number: int
    version: int
