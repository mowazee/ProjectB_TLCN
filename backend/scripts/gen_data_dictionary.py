"""Sinh từ điển dữ liệu (docs/DATA_DICTIONARY.md) từ model SQLAlchemy - luôn khớp với mã nguồn và migration.

Chạy (trong backend/):  .venv\\Scripts\\python.exe scripts/gen_data_dictionary.py
CI không chạy script này; sinh lại khi đổi model (cùng PR với migration).
"""

import sys
from pathlib import Path

from sqlalchemy import Enum, UniqueConstraint
from sqlalchemy.dialects import postgresql

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.main  # noqa: E402,F401 - nạp mọi module để đăng ký model vào metadata
from app.shared.db import Base  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "docs" / "DATA_DICTIONARY.md"


def _module(table) -> str:  # type: ignore[no-untyped-def]
    for mapper in Base.registry.mappers:
        if mapper.local_table is table:
            parts = mapper.class_.__module__.split(".")
            return parts[2] if len(parts) > 2 and parts[1] == "modules" else "-"
    return "- (bảng gắn cột/khai báo bằng Table)"


def _type(col) -> str:  # type: ignore[no-untyped-def]
    t = col.type
    if isinstance(t, Enum) and t.enums:
        return f"VARCHAR({t.length}) ∈ {{{', '.join(t.enums)}}}"
    try:
        return str(t.compile(dialect=postgresql.dialect()))  # kiểu như trên PostgreSQL triển khai thật
    except Exception:  # noqa: BLE001 - kiểu tùy biến không compile được ngoài dialect
        return type(t).__name__


def _fk(col) -> str:  # type: ignore[no-untyped-def]
    out = []
    for fk in col.foreign_keys:
        rule = f" ON DELETE {fk.ondelete}" if fk.ondelete else ""
        out.append(f"→ {fk.target_fullname}{rule}")
    return "; ".join(out)


def main() -> None:
    tables = sorted(Base.metadata.tables.values(), key=lambda t: t.name)
    lines = [
        "# Từ điển dữ liệu",
        "",
        "Sinh tự động bằng `backend/scripts/gen_data_dictionary.py` từ model SQLAlchemy (khớp migration Alembic, "
        "kiểm tra bằng `alembic check` trong CI). Ý nghĩa nghiệp vụ của từng bảng: file 3 mục IV "
        "(bảng mô tả thực thể); quy tắc nghiệp vụ: [BUSINESS_RULES.md](BUSINESS_RULES.md).",
        "",
        f"Tổng số bảng: **{len(tables)}**.",
        "",
        "| Bảng | Module | Số cột |",
        "|---|---|---|",
    ]
    lines += [f"| [`{t.name}`](#{t.name.replace('_', '-')}) | {_module(t)} | {len(t.columns)} |" for t in tables]
    for t in tables:
        header = "| Cột | Kiểu | Null | Khóa / tham chiếu | Mặc định |"
        lines += ["", f"## {t.name}", "", header, "|---|---|---|---|---|"]
        pk = {c.name for c in t.primary_key.columns}
        for c in t.columns:
            key = ", ".join(x for x in ["PK" if c.name in pk else "", "UNIQUE" if c.unique else "", _fk(c)] if x)
            default = ""
            if c.server_default is not None:
                default = str(getattr(c.server_default, "arg", "")).strip("'")
            elif c.default is not None and getattr(c.default, "is_scalar", False):
                default = str(getattr(c.default, "arg", ""))
            null = "không" if not c.nullable else "có"
            lines.append(f"| `{c.name}` | {_type(c)} | {null} | {key} | {default} |")
        extra = []
        for idx in sorted(t.indexes, key=lambda i: i.name or ""):
            extra.append(
                f"- Index `{idx.name}`: ({', '.join(c.name for c in idx.columns)})" + (" UNIQUE" if idx.unique else "")
            )
        uniques = [c for c in t.constraints if isinstance(c, UniqueConstraint) and len(c.columns) > 1]
        for u in uniques:
            extra.append(f"- UNIQUE `{u.name}`: ({', '.join(c.name for c in u.columns)})")
        if extra:
            lines += ["", *extra]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"Đã ghi {OUT} ({len(tables)} bảng)")


if __name__ == "__main__":
    main()
