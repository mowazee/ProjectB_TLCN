"""FR-15 / P2-08 (SDD v0.13): gom các file của lô thành "bộ hồ sơ" (Python thuần).

Mỗi bộ = một tài liệu chính (OCR) + tài liệu đi kèm (không OCR). Hai cách khai báo:

1. manifest.csv (ưu tiên khi có): cột file_name (file chính), attachments (tên file đi kèm, phân cách ";"),
   title, category, document_code; từ v0.14 (FR-19) thêm validity (effective | effective_until | expired |
   unspecified) và valid_until (yyyy-mm-dd hoặc dd/mm/yyyy).
   File đi kèm khai báo mà không có trong lô → lỗi riêng bộ đó.
2. Quy ước thư mục trong ZIP: thư mục con cấp 1 là một bộ khi có thư mục "dinh-kem/" hoặc file "main.*":
   - file chính = "main.*", hoặc file duy nhất ở gốc thư mục;
   - gốc thư mục chỉ có nhiều ảnh, không có main.* → gộp các ảnh theo thứ tự tên file thành một tài liệu (FR-16);
   - còn lại (nhiều file ở gốc, không xác định được file chính) → lỗi bộ đó;
   - mọi file trong "dinh-kem/" là tài liệu đi kèm.
File không thuộc bộ nào được nhập riêng lẻ như trước v0.13.
"""

import csv
import io
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from app.modules.imports.domain.archive import ArchiveError, Entry

ATTACH_DIR = "dinh-kem"
IMAGE_EXT = (".png", ".jpg", ".jpeg")


@dataclass
class Bundle:
    key: str  # tên hiển thị trong báo cáo (đường dẫn file chính hoặc thư mục)
    main: list[Entry] = field(default_factory=list)  # 1 file, hoặc nhiều ảnh sẽ gộp
    attachments: list[Entry] = field(default_factory=list)
    row: dict[str, str] = field(default_factory=dict)  # dòng manifest/metadata (title, category, document_code)
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


def _split(entry: Entry) -> tuple[str, list[str]] | None:
    """(khóa thư mục bộ, phần đường dẫn bên trong thư mục) cho file trong ZIP có thư mục con cấp 1."""
    parts = entry.name.replace("\\", "/").split("/")
    zip_idx = next((i for i, p in enumerate(parts) if p.lower().endswith(".zip")), None)
    if zip_idx is None or len(parts) - zip_idx < 3:  # cần zip/thư-mục/file
        return None
    return "/".join(parts[: zip_idx + 2]), parts[zip_idx + 2 :]


def _from_folders(entries: list[Entry]) -> tuple[list[Bundle], list[Entry]]:
    groups: dict[str, list[tuple[list[str], Entry]]] = {}
    for e in entries:
        sp = _split(e)
        if sp:
            groups.setdefault(sp[0], []).append((sp[1], e))
    bundles: list[Bundle] = []
    used: set[int] = set()
    for key, items in groups.items():
        root = [e for rest, e in items if len(rest) == 1]
        atts = [e for rest, e in items if len(rest) >= 2 and rest[0].lower() == ATTACH_DIR]
        mains = [e for e in root if PurePosixPath(e.filename).stem.lower() == "main"]
        if not atts and not mains:
            continue  # thư mục thường: nhập riêng lẻ như trước
        b = Bundle(key=key, attachments=atts)
        if len(mains) == 1:
            b.main = mains
        elif len(root) == 1:
            b.main = root
        elif root and not mains and all(e.filename.lower().endswith(IMAGE_EXT) for e in root):
            b.main = sorted(root, key=lambda e: e.filename.lower())
        else:
            b.error_code = "BUNDLE_NO_MAIN"
            b.error_message = "Không xác định được file chính (đặt tên main.* hoặc chỉ để một file ở gốc thư mục)"
        bundles.append(b)
        # file ở gốc khác main.* (khi đã có main) được nhập riêng lẻ; bộ lỗi giữ mọi file để báo cáo đúng bộ
        used.update(id(e) for e in [*(root if b.error_code else b.main), *atts])
    return bundles, [e for e in entries if id(e) not in used]


def group(entries: list[Entry], manifest: bytes | None) -> tuple[list[Bundle], list[Entry]]:
    """Trả (các bộ, các file lẻ còn lại). Entry đã có lỗi (ZIP không an toàn...) luôn là file lẻ."""
    ok = [e for e in entries if not e.error_code]
    bad = [e for e in entries if e.error_code]
    rows = parse_manifest(manifest)
    bundles, rest = _from_manifest(ok, rows) if rows else _from_folders(ok)
    return bundles, rest + bad
