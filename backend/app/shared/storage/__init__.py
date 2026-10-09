"""StoragePort + LocalStorage (private storage, ngoài mọi thư mục static).

Khóa do hệ thống sinh; client không bao giờ nhận storage_key hay đường dẫn nội bộ
(SDD mục 7, 14). Có thể thay bằng MinIO/S3 bằng một lớp hiện thực khác của StoragePort.
"""

import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Protocol

from app.shared.config import settings
from app.shared.errors import StorageError


class StoragePort(Protocol):
    def save_bytes(self, key: str, data: bytes) -> None: ...
    def read_bytes(self, key: str) -> bytes: ...
    def path(self, key: str) -> Path: ...
    def exists(self, key: str) -> bool: ...
    def delete(self, key: str) -> None: ...
    def delete_prefix(self, prefix: str) -> None: ...


def original_key(document_id: uuid.UUID, ext: str) -> str:
    return f"documents/{document_id}/original.{ext}"


def page_image_key(document_id: uuid.UUID, page_number: int) -> str:
    return f"documents/{document_id}/pages/{page_number:04d}.png"


def document_prefix(document_id: uuid.UUID) -> str:
    return f"documents/{document_id}"


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()

    def _resolve(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):
            raise StorageError("Khóa lưu trữ không hợp lệ")
        return path

    def save_bytes(self, key: str, data: bytes) -> None:
        """Ghi atomic: file tạm rồi đổi tên."""
        path = self._resolve(key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            os.replace(tmp, path)
        except OSError as exc:
            raise StorageError("Không lưu được file") from exc

    def path(self, key: str) -> Path:
        path = self._resolve(key)
        if not path.is_file():
            raise StorageError("Không tìm thấy file trong kho lưu trữ", code="FILE_NOT_FOUND")
        return path

    def read_bytes(self, key: str) -> bytes:
        return self.path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._resolve(key).is_file()

    def delete(self, key: str) -> None:
        self._resolve(key).unlink(missing_ok=True)

    def delete_prefix(self, prefix: str) -> None:
        target = self._resolve(prefix)
        if target.exists():
            shutil.rmtree(target)


def get_storage() -> StoragePort:
    return LocalStorage(settings.STORAGE_ROOT)
