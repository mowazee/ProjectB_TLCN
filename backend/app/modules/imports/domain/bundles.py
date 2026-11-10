"""P2-08 (SDD v0.14): gom file của lô thành "bộ hồ sơ" theo manifest.csv - cách khai báo duy nhất (Python thuần).

Mỗi dòng manifest.csv = một tài liệu chính (OCR) + tài liệu đi kèm (không OCR, FR-15). Cột: file_name (bắt buộc, tên
file chính), attachments (tên file đi kèm, phân cách ";"), title, category (mã danh mục), document_code, validity
(effective | effective_until | expired | unspecified) và valid_until (yyyy-mm-dd hoặc dd/mm/yyyy) - FR-19.
Lô không có manifest.csv bị từ chối (MANIFEST_REQUIRED); file khai báo mà không có trong lô chỉ làm lỗi dòng đó; file có
trong lô nhưng không được khai báo bị bỏ qua và báo lỗi NOT_IN_MANIFEST. v0.14 bỏ quy ước thư mục và metadata.csv.
"""

import csv
import io
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from app.modules.imports.domain.archive import ArchiveError, Entry


@dataclass
class Bundle:
    key: str  # tên hiển thị trong báo cáo (đường dẫn file chính)
    main: list[Entry] = field(default_factory=list)  # file chính
    attachments: list[Entry] = field(default_factory=list)
    row: dict[str, str] = field(default_factory=dict)  # dòng manifest.csv
    error_code: str | None = None
    error_message: str | None = None


def parse_manifest(data: bytes | None) -> list[dict[str, str]]:
    if not data:
        return []
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ArchiveError("METADATA_INVALID", "manifest.csv phải mã hóa UTF-8") from exc
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or "file_name" not in [f.strip().lower() for f in reader.fieldnames]:
        raise ArchiveError("METADATA_INVALID", "manifest.csv thiếu cột file_name")
    rows = []
    for row in reader:
        clean = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        if clean.get("file_name"):
            rows.append(clean)
    return rows


def _base(name: str) -> str:
    return PurePosixPath(name.replace("\\", "/")).name.lower()


def _from_manifest(entries: list[Entry], rows: list[dict[str, str]]) -> tuple[list[Bundle], list[Entry]]:
    by_name: dict[str, Entry] = {}
    for e in entries:
        by_name.setdefault(e.filename.lower(), e)
    used: set[int] = set()
    bundles = []
    for row in rows:
        main = by_name.get(_base(row["file_name"]))
        b = Bundle(key=main.name if main else row["file_name"], row=row)
        if main is None:
            b.error_code, b.error_message = "FILE_NOT_FOUND", f"Không có file chính '{row['file_name']}' trong lô"
        else:
            b.main = [main]
            used.add(id(main))
        missing = []
        for name in [x.strip() for x in row.get("attachments", "").split(";") if x.strip()]:
            att = by_name.get(_base(name))
            if att is None:
                missing.append(name)
            else:
                b.attachments.append(att)
                used.add(id(att))
        if missing and not b.error_code:
            b.error_code = "ATTACHMENT_NOT_FOUND"
            b.error_message = "Không có file đi kèm trong lô: " + ", ".join(missing)
        bundles.append(b)
    return bundles, [e for e in entries if id(e) not in used]


def group(entries: list[Entry], manifest: bytes | None) -> tuple[list[Bundle], list[Entry]]:
    """Trả (các bộ theo manifest, các file lỗi). File không khai báo trong manifest -> NOT_IN_MANIFEST; entry đã có
    lỗi (ZIP không an toàn...) giữ lỗi của nó."""
    rows = parse_manifest(manifest)
    if not rows:
        raise ArchiveError("MANIFEST_REQUIRED", "Lô phải có manifest.csv khai báo các file cần nhập (cột file_name)")
    ok = [e for e in entries if not e.error_code]
    bad = [e for e in entries if e.error_code]
    bundles, rest = _from_manifest(ok, rows)
    for e in rest:
        e.error_code, e.error_message = "NOT_IN_MANIFEST", "File không được khai báo trong manifest.csv, bỏ qua"
    return bundles, rest + bad
