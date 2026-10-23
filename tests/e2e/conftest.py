"""E2E Playwright (NFR-07): chạy trên hệ thống thật đang chạy (React -> API -> worker -> DB).

    BASE_URL=http://127.0.0.1:8080 pytest tests/e2e --browser chromium

Tài khoản lấy từ scripts/seed_demo.py. Tài liệu kiểm thử TỰ SINH (PDF có lớp chữ: không cần model OCR).
"""

import os
import re
import uuid

import pymupdf
import pytest
from playwright.sync_api import Browser, Page, expect

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8080").rstrip("/")
ADMIN = ("admin", os.environ.get("DEMO_ADMIN_PASSWORD", "Admin@12345"))
OFFICER = ("nhanvien", "Demo@12345")
APPROVER = ("kiemduyet", "Demo@12345")
OTHER_DEPT_OFFICER = ("ketoan", "Demo@12345")  # Phòng Kế toán (FR-13: người phòng khác)
FONT = next(
    (f for f in ("C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf") if os.path.exists(f)),
    None,
)


def make_pdf(path, lines: list[str]) -> str:
    doc = pymupdf.open()
    page = doc.new_page()
    if FONT:
        page.insert_font(fontname="vn", fontfile=FONT)
    for i, line in enumerate(lines):
        page.insert_text((60, 80 + 24 * i), line, fontname="vn" if FONT else "helv", fontsize=12)
    doc.save(str(path))
    return str(path)


def login(page: Page, user: tuple[str, str]) -> None:
    page.goto(f"{BASE_URL}/login")
    page.get_by_label("Tên đăng nhập hoặc email").fill(user[0])
    page.get_by_label("Mật khẩu").fill(user[1])
    page.get_by_role("button", name="Đăng nhập").click()
    expect(page.get_by_role("button", name="Đăng xuất")).to_be_visible()


def features(page: Page) -> list[str]:
    # fetch trong trình duyệt (không dùng page.request): cookie session có cờ Secure ở production; trình duyệt
    # vẫn gửi nó tới http://127.0.0.1 (nguồn tin cậy), còn APIRequestContext của Playwright thì không.
    return page.evaluate("fetch('/api/auth/me').then(r => r.json()).then(b => b.features)")


def choose_category(page: Page, category: str) -> None:
    """D-10: khi bật phân loại tự động, mặc định Danh mục gợi ý - chuyển sang tự chọn để có ô chọn danh mục."""
    page.locator("select[name=category_id], [role=radio]").first.wait_for()
    mine = page.get_by_role("radio", name="Tôi chọn danh mục")
    if mine.count():
        mine.click()
    page.locator("select[name=category_id]").select_option(label=category)


def upload_and_wait(page: Page, pdf_path: str, title: str, category: str | None = None) -> str:
    """Upload qua giao diện, chờ job OCR hoàn tất; trả document_id.

    category=None: giữ "Danh mục gợi ý" khi phân loại tự động bật - tài liệu nguồn auto/pending không bao giờ thành
    mẫu huấn luyện (D-10), nên văn bản thử nghiệm không dạy sai mô hình trên dữ liệu demo; cờ tắt thì chọn Hợp đồng."""
    page.goto(f"{BASE_URL}/documents/new")
    page.locator("input[name=file]").set_input_files(pdf_path)
    page.get_by_label("Tiêu đề").fill(title)
    page.locator("select[name=category_id], [role=radio]").first.wait_for()
    if category or not page.get_by_role("radio", name=re.compile("Danh mục gợi ý")).count():
        choose_category(page, category or "Hợp đồng")
    page.get_by_role("button", name="Tải lên").click()
    page.get_by_role("link", name="Mở tài liệu").click()
    expect(page.get_by_text("Hoàn tất").first).to_be_visible(timeout=90_000)
    match = re.search(r"/documents/([0-9a-f-]{36})", page.url)
    assert match, page.url
    return match.group(1)


@pytest.fixture
def uniq() -> str:
    return uuid.uuid4().hex[:8]


@pytest.fixture
def officer_page(page: Page) -> Page:
    login(page, OFFICER)
    return page


@pytest.fixture
def new_context_page(browser: Browser):
    contexts = []

    def _open(user: tuple[str, str]) -> Page:
        ctx = browser.new_context()
        contexts.append(ctx)
        p = ctx.new_page()
        login(p, user)
        return p

    yield _open
    for c in contexts:
        c.close()
