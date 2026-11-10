"""FR-14 (SDD v0.13): khoảng hợp lệ của thời gian lưu trữ (Python thuần)."""

TRASH_KEY = "trash_retention_days"
AUDIT_KEY = "audit_retention_days"
LIMITS: dict[str, tuple[int, int]] = {TRASH_KEY: (1, 365), AUDIT_KEY: (180, 3650)}
LABELS = {TRASH_KEY: "Thời gian giữ tài liệu trong thùng rác", AUDIT_KEY: "Thời gian lưu audit log"}


def violations(values: dict[str, int]) -> dict[str, str]:
    """Trả {key: lý do} cho giá trị ngoài khoảng."""
    out = {}
    for key, value in values.items():
        lo, hi = LIMITS[key]
        if not lo <= value <= hi:
            out[key] = f"{LABELS[key]} phải từ {lo} đến {hi} ngày"
    return out
