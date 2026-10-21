"""Luồng MVP end to end (SDD mục 9 DoD: đăng nhập -> upload -> job OCR -> sửa -> tìm kiếm -> preview)."""

from playwright.sync_api import Page, expect

from conftest import BASE_URL, OFFICER, choose_category, login, make_pdf, upload_and_wait


def test_login_reload_and_logout(page: Page):
    page.goto(f"{BASE_URL}/documents")
    expect(page).to_have_url(f"{BASE_URL}/login")  # chưa đăng nhập -> /login
    login(page, OFFICER)
    expect(page).to_have_url(f"{BASE_URL}/documents")  # quay lại route dự định
    page.reload()  # cookie HttpOnly giữ đăng nhập sau reload
    expect(page.get_by_role("heading", name="Tài liệu")).to_be_visible()
    page.get_by_role("button", name="Đăng xuất").click()
    expect(page).to_have_url(f"{BASE_URL}/login")
    page.goto(f"{BASE_URL}/documents")
    expect(page).to_have_url(f"{BASE_URL}/login")


def test_upload_ocr_edit_search_preview(officer_page: Page, tmp_path, uniq):
    page = officer_page
    word = f"kiemthu{uniq}"
    pdf = make_pdf(tmp_path / "e2e.pdf", ["Biên bản nghiệm thu E2E", f"Mã kiểm thử {word} công trình số 7"])
    doc_id = upload_and_wait(page, pdf, f"E2E {uniq}")

    # Preview trang + reload URL sâu
    page.goto(f"{BASE_URL}/documents/{doc_id}/pages/1")
    page.reload()
    expect(page.get_by_text(word)).to_be_visible()

    # Sửa OCR -> version mới
    page.get_by_role("link", name="Sửa OCR").click()
    editor = page.get_by_label("Nội dung OCR")
    editor.fill(editor.input_value() + f"\nĐã hiệu đính {uniq}")
    page.get_by_role("button", name="Lưu phiên bản mới").click()
    expect(page.get_by_text("v1")).to_be_visible()

    # Tìm kiếm không dấu trên text hiệu lực, mở đúng trang kèm từ khóa
    page.goto(f"{BASE_URL}/search")
    page.get_by_label("Từ khóa").fill(f"da hieu dinh {uniq}")
    page.get_by_role("link", name="Trang 1").click()
    page.wait_for_url(f"**/documents/{doc_id}/pages/1?q=*")
    expect(page.get_by_text(f"Đã hiệu đính {uniq}")).to_be_visible()


def test_upload_rejects_fake_pdf(officer_page: Page, tmp_path):
    fake = tmp_path / "gia.pdf"
    fake.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 100)
    page = officer_page
    page.goto(f"{BASE_URL}/documents/new")
    page.locator("input[name=file]").set_input_files(str(fake))
    choose_category(page, "Hợp đồng")
    page.get_by_role("button", name="Tải lên").click()
    expect(page.get_by_role("alert")).to_contain_text("Loại file không được hỗ trợ")


def test_concurrent_edit_409_keeps_draft(officer_page: Page, new_context_page, tmp_path, uniq):
    doc_id = upload_and_wait(officer_page, make_pdf(tmp_path / "c.pdf", [f"Xung đột {uniq} nội dung gốc dài"]), f"409 {uniq}")
    a = officer_page
    b = new_context_page(OFFICER)
    for p in (a, b):
        p.goto(f"{BASE_URL}/documents/{doc_id}/pages/1/edit")
    a.get_by_label("Nội dung OCR").fill("Bản của A")
    a.get_by_role("button", name="Lưu phiên bản mới").click()
    expect(a).to_have_url(f"{BASE_URL}/documents/{doc_id}/pages/1")
    b.get_by_label("Nội dung OCR").fill("Bản nháp của B")
    b.get_by_role("button", name="Lưu phiên bản mới").click()
    expect(b.get_by_text("đã được người khác cập nhật")).to_be_visible()
    expect(b.get_by_label("Nội dung OCR")).to_have_value("Bản nháp của B")
    b.get_by_role("button", name="Tải bản mới nhất để so sánh").click()
    expect(b.get_by_text("Bản của A")).to_be_visible()


def test_cross_scope_403(new_context_page, officer_page: Page, tmp_path, uniq):
    doc_id = upload_and_wait(officer_page, make_pdf(tmp_path / "s.pdf", [f"Phạm vi {uniq} tài liệu riêng"]), f"Scope {uniq}")
    other = new_context_page(("ketoan", "Demo@12345"))  # phòng Kế toán
    other.goto(f"{BASE_URL}/documents/{doc_id}")
    expect(other.get_by_role("alert")).to_contain_text("không có quyền")
