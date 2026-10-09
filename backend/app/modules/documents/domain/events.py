"""Domain event của module documents (phát sau commit, Đặc tả đề tài v0.5 mục 4.3)."""

import uuid
from dataclasses import dataclass

from app.shared.domain_events import Event


@dataclass(frozen=True)
class DocumentUploaded(Event):
    document_id: uuid.UUID
    owner_id: uuid.UUID | None


@dataclass(frozen=True)
class DocumentDeleted(Event):
    document_id: uuid.UUID


@dataclass(frozen=True)
class DocumentRestored(Event):
    document_id: uuid.UUID


@dataclass(frozen=True)
class DocumentPurged(Event):
    document_id: uuid.UUID
