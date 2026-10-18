"""Nạp dữ liệu mẫu cho demo. Chạy lại nhiều lần an toàn (bỏ qua phần đã có).

    python scripts/seed_demo.py              # tài khoản + danh mục + kho lưu trữ + tài liệu mẫu
    python scripts/seed_demo.py --admin-only # chỉ tạo tài khoản Admin đầu tiên (môi trường thật)

Tài liệu mẫu TỰ SINH (không dùng tài liệu thật, NFR-02). Tài liệu được đưa vào hàng đợi OCR như khi
upload từ giao diện; worker xử lý ở nền. Mật khẩu Admin lấy từ biến DEMO_ADMIN_PASSWORD nếu có.
"""

import argparse
import io
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pymupdf
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import registry
from app.modules.borrowing.application import locations
from app.modules.categories.application.manage import create_category, list_categories
from app.modules.documents.application.queries import visible_document_ids
from app.modules.documents.application.upload import create_document_from_bytes
from app.modules.users.application.manage import (
    create_department,
    create_user,
    find_first_admin,
    get_user,
    list_departments,
    seed_reference_data,
)
from app.modules.users.application.queries import find_credentials, to_principal
from app.shared.config import settings
from app.shared.context import Principal, RequestContext
from app.shared.db import SessionLocal

CTX = RequestContext(user_agent="seed-demo")
ADMIN_PASSWORD = os.environ.get("DEMO_ADMIN_PASSWORD", "Admin@12345")
USER_PASSWORD = "Demo@12345"  # mật khẩu tài khoản demo, ghi trong README
USERS = [  # username, họ tên, vai trò, mã phòng ban
    ("nhanvien", "Nguyễn Văn Nghiệp Vụ", "OFFICER", "HC-TH"),
    ("kiemduyet", "Trần Thị Kiểm Duyệt", "APPROVER", "HC-TH"),
    ("ketoan", "Lê Văn Kế Toán", "OFFICER", "KT"),
    ("nguoidung", "Phạm Thị Người Dùng", "VIEWER", "HC-TH"),  # FR-12: chỉ xem tài liệu đã xuất bản cùng phòng ban
]
CATEGORIES = [  # mã, tên, số năm lưu trữ, mô tả (mô tả giúp P2-05 gợi ý khi chưa có dữ liệu)
    ("HOP-DONG", "Hợp đồng", 10, "hợp đồng kinh tế mua bán thuê dịch vụ bên A bên B giá trị thanh toán"),
    ("CONG-VAN", "Công văn", 5, "công văn v/v kính gửi đề nghị các phòng ban triển khai"),
    ("QUYET-DINH", "Quyết định", 20, "quyết định bổ nhiệm ban hành quy chế căn cứ điều khoản"),
    ("BAO-CAO", "Báo cáo - Biên bản", 5, "báo cáo biên bản nghiệm thu cuộc họp kết luận"),
    ("HOA-DON", "Hóa đơn - Chứng từ", 10, "hóa đơn giá trị gia tăng ký hiệu số tiền thanh toán thuế"),
]
LOCATIONS = [("KHO-A1", "Kho A - Kệ 1"), ("KHO-A2", "Kho A - Kệ 2"), ("KHO-B1", "Kho B - Tủ hồ sơ 1")]
FONT = next(
    (f for f in ("C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf") if Path(f).exists()),
    None,
)


# ---------------------------------------------------------------- tài liệu mẫu tự sinh
def _image(lines: list[str], size: tuple[int, int], rotate: float = 0.0) -> Image.Image:
    img = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, 40) if FONT else ImageFont.load_default()
    for i, line in enumerate(lines):
        draw.text((80, 70 + 90 * i), line, fill="black", font=font)
    return img.rotate(rotate, fillcolor="white") if rotate else img


def _png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def scanned_contract_pdf() -> bytes:
    """PDF chỉ có ảnh, nghiêng 1.5 độ: giả lập bản scan, phải OCR."""
    img = _image(
        [
            "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM",
            "HỢP ĐỒNG KINH TẾ",
            "Số: 123/2026/HĐ-KT",
            "BÊN A: Công ty TNHH Số hóa Tài liệu Việt",
            "BÊN B: Công ty Cổ phần Lưu trữ Bình Minh",
            "Giá trị hợp đồng: 150.000.000 VND",
        ],
        (1650, 700),
        rotate=1.5,
    )
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=252)
    page.insert_image(page.rect, stream=_png(img))
    return bytes(doc.tobytes())


def digital_report_pdf() -> bytes:
    """PDF có lớp chữ, 2 trang: lấy text trực tiếp, không OCR."""
    doc = pymupdf.open()
    pages = [
        [
            "BIÊN BẢN NGHIỆM THU CÔNG TRÌNH",
            "Công trình: Nhà lớp học 3 tầng trường THCS Bình Minh",
            "Thời gian: 08 giờ 00 ngày 25 tháng 9 năm 2026",
            "Thành phần: Đại diện chủ đầu tư, đơn vị thi công, đơn vị giám sát",
        ],
        [
            "KẾT LUẬN",
            "Công trình đạt yêu cầu kỹ thuật, đồng ý nghiệm thu đưa vào sử dụng.",
            "Biên bản lập thành 04 bản có giá trị pháp lý như nhau.",
        ],
    ]
    for lines in pages:
        page = doc.new_page()
        if FONT:
            page.insert_font(fontname="vn", fontfile=FONT)
        for i, line in enumerate(lines):
            page.insert_text((60, 80 + 28 * i), line, fontname="vn" if FONT else "helv", fontsize=13)
    return bytes(doc.tobytes())


def official_letter_png() -> bytes:
    return _png(
        _image(
            [
                "CÔNG TY TNHH SỐ HÓA TÀI LIỆU VIỆT",
                "Số: 45/CV-HCTH",
                "Hà Nội, ngày 15 tháng 9 năm 2026",
                "V/v triển khai số hóa hồ sơ tài liệu năm 2026",
                "Kính gửi: Các phòng ban trong công ty",
            ],
            (1650, 560),
        )
    )


def invoice_png() -> bytes:
    return _png(
        _image(
            ["HÓA ĐƠN GIÁ TRỊ GIA TĂNG", "Ký hiệu: 1C26TAA   Số: 0000789", "Tổng tiền thanh toán: 27.500.000 đồng"],
            (1650, 420),
        )
    )


SAMPLES = [  # tên file, tiêu đề, mã danh mục, người upload, hàm sinh, vị trí kho
    ("hop-dong-kinh-te.pdf", "Hợp đồng kinh tế số 123/2026", "HOP-DONG", "nhanvien", scanned_contract_pdf, "KHO-A1"),
    ("bien-ban-nghiem-thu.pdf", "Biên bản nghiệm thu công trình", "BAO-CAO", "nhanvien", digital_report_pdf, "KHO-A2"),
    ("cong-van-45.png", "Công văn 45/CV-HCTH về số hóa", "CONG-VAN", "nhanvien", official_letter_png, "KHO-A1"),
    ("hoa-don-0000789.png", "Hóa đơn GTGT số 0000789", "HOA-DON", "ketoan", invoice_png, "KHO-B1"),
]


# ---------------------------------------------------------------- nạp dữ liệu
def _principal(db: Session, admin: Principal, username: str) -> Principal:
    cred = find_credentials(db, username)
    if cred is None:
        raise SystemExit(f"Thiếu tài khoản {username}")
    return to_principal(get_user(db, admin, cred.user_id))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--admin-only", action="store_true")
    parser.add_argument(
        "--allow-demo-in-production",
        action="store_true",
        help="cho phép tạo tài khoản/tài liệu demo khi APP_ENV=production (chỉ dùng thử nghiệm)",
    )
    args = parser.parse_args()
    if settings.is_production:
        if not os.environ.get("DEMO_ADMIN_PASSWORD"):
            print("APP_ENV=production: phải đặt DEMO_ADMIN_PASSWORD (không dùng mật khẩu mặc định)", file=sys.stderr)
            return 2
        if not args.admin_only and not args.allow_demo_in_production:
            print("APP_ENV=production: chỉ chạy --admin-only (tài khoản demo có mật khẩu công khai)", file=sys.stderr)
            return 2
    registry.activate()
    with SessionLocal() as db:
        seed_reference_data(db)
        admin_user = find_first_admin(db)
        if admin_user is None:
            admin_user = create_user(
                db,
                None,
                username="admin",
                email="admin@example.com",
                full_name="Quản trị viên",
                password=ADMIN_PASSWORD,
                roles=["ADMIN"],
                ctx=CTX,
            )
            print("+ Tài khoản admin")
        if args.admin_only:
            return 0
        admin = to_principal(admin_user)

        deps = {d.code: d.id for d in list_departments(db)}
        if "KT" not in deps:
            deps["KT"] = create_department(db, admin, code="KT", name="Phòng Kế toán", ctx=CTX).id
            print("+ Phòng ban Phòng Kế toán")
        for username, full_name, role, dep in USERS:
            if find_credentials(db, username) is None:
                create_user(
                    db,
                    admin,
                    username=username,
                    email=f"{username}@example.com",
                    full_name=full_name,
                    password=USER_PASSWORD,
                    roles=[role],
                    department_id=deps[dep],
                    ctx=CTX,
                )
                print(f"+ Tài khoản {username}")

        cats = {c.code: c for c in list_categories(db)}
        for code, name, years, desc in CATEGORIES:
            if code not in cats:
                cats[code] = create_category(
                    db, admin, {"code": code, "name": name, "retention_period_years": years, "description": desc}, CTX
                )
                print(f"+ Danh mục {name}")

        locs = {x.code: x for x in locations.list_locations(db)}
        for code, name in LOCATIONS:
            if code not in locs:
                locs[code] = locations.create_location(db, admin, name=name, code=code, ctx=CTX)
                print(f"+ Vị trí lưu trữ {name}")

        if db.scalar(select(func.count()).select_from(visible_document_ids(admin).subquery())):
            print("= Đã có tài liệu, không tạo thêm tài liệu mẫu")
            return 0
        for filename, title, cat, owner, make, loc in SAMPLES:
            p = _principal(db, admin, owner)
            doc, job = create_document_from_bytes(
                db,
                p,
                data=make(),
                filename=filename,
                title=title,
                category_id=cats[cat].id,
                is_handwritten=False,
                ctx=CTX,
            )
            locations.set_document_location(db, p, doc.id, locs[loc].id, CTX)
            print(f"+ Tài liệu '{title}' -> hàng đợi OCR (job {str(job.id)[:8]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
