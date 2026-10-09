"""Xuất OpenAPI (bật mọi cờ P2) ra docs/openapi.json để sinh types cho React (SDD mục 7, 13).

python scripts/export_openapi.py [đường_dẫn_ra]
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SESSION_BACKEND", "memory")
os.environ["FEATURES_ENABLED"] = (
    "workflow,highlight,handwriting,extraction,classification,versions,borrowing,notifications,imports,rollback"
)

from app.main import create_app  # noqa: E402


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "docs" / "openapi.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    spec = create_app().openapi()
    out.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Đã ghi {out} ({len(spec['paths'])} path)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
