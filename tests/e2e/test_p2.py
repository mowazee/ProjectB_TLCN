"""Luồng P2 end to end; mỗi test tự bỏ qua khi cờ tương ứng đang tắt (NFR-09, e2e.yml matrix)."""

import io
import zipfile

import pytest
from playwright.sync_api import Page, expect

from conftest import ADMIN, APPROVER, BASE_URL, OTHER_DEPT_OFFICER, features, login, make_pdf, upload_and_wait


def need(page: Page, *flags: str) -> None:
    missing = [f for f in flags if f not in features(page)]
    if missing:
        pytest.skip(f"cờ tắt: {missing}")


def test_p2_flags_off_hide_screens(officer_page: Page):
    page = officer_page
    if "workflow" in features(page):
        pytest.skip("workflow đang bật")
    page.goto(f"{BASE_URL}/reviews")
    expect(page.get_by_text("Không tìm thấy trang")).to_be_visible()


def test_workflow_submit_approve_publish(officer_page: Page, new_context_page, tmp_path, uniq):
    need(officer_page, "workflow")
    doc_id = upload_and_wait(officer_page, make_pdf(tmp_path / "w.pdf", [f"Quyết định {uniq} ban hành"]), f"Duyệt {uniq}")
    officer_page.get_by_role("button", name="Gửi duyệt").click()
    officer_page.get_by_role("button", name="Xác nhận").click()
    expect(officer_page.get_by_text("Chờ duyệt").first).to_be_visible()

    approver = new_context_page(APPROVER)
    approver.goto(f"{BASE_URL}/reviews")
    approver.get_by_role("link", name=f"Duyệt {uniq}").click()
    approver.get_by_role("button", name="Duyệt", exact=True).click()
    approver.get_by_role("button", name="Xác nhận").click()
    approver.get_by_role("button", name="Xuất bản").click()
    approver.get_by_role("button", name="Xác nhận").click()
    expect(approver.get_by_text("Đã xuất bản").first).to_be_visible()
    approver.get_by_role("tab", name="Lịch sử duyệt").click()
    expect(approver.get_by_role("cell", name="Xuất bản")).to_be_visible()
    assert doc_id


def test_share_published_document_across_departments(officer_page: Page, new_context_page, tmp_path, uniq):
    """FR-13: chủ sở hữu chia sẻ Toàn hệ thống -> phòng khác thấy ở "Được chia sẻ với tôi"; Riêng tư -> mất quyền."""
    need(officer_page, "workflow")
    title = f"Chia sẻ {uniq}"
    doc_id = upload_and_wait(officer_page, make_pdf(tmp_path / "s.pdf", [f"Biên bản {uniq}"]), title)
    expect(officer_page.get_by_role("button", name="Chia sẻ", exact=True)).to_be_disabled()  # chưa xuất bản
    officer_page.get_by_role("button", name="Gửi duyệt").click()
    officer_page.get_by_role("button", name="Xác nhận").click()
    approver = new_context_page(APPROVER)
    approver.goto(f"{BASE_URL}/documents/{doc_id}")
    for action in ("Duyệt", "Xuất bản"):
        approver.get_by_role("button", name=action, exact=True).click()
        approver.get_by_role("button", name="Xác nhận").click()
    expect(approver.get_by_text("Đã xuất bản").first).to_be_visible()

    other = new_context_page(OTHER_DEPT_OFFICER)
    other.goto(f"{BASE_URL}/documents/{doc_id}")
    expect(other.get_by_role("alert")).to_be_visible()  # mặc định Nội bộ: phòng khác chưa thấy

    officer_page.reload()
    officer_page.get_by_role("button", name="Chia sẻ", exact=True).click()
    dialog = officer_page.get_by_role("dialog")
    dialog.get_by_role("radio", name="Toàn hệ thống").click()
    dialog.get_by_role("button", name="Lưu thay đổi").click()
    expect(dialog).to_have_count(0)
    expect(officer_page.get_by_text("Toàn hệ thống").first).to_be_visible()

    other.goto(f"{BASE_URL}/documents?shared=with_me")
    other.get_by_role("link", name=title).click()
    expect(other.get_by_role("heading", name=title)).to_be_visible()
    expect(other.get_by_role("button", name="Sửa thông tin")).to_have_count(0)  # chia sẻ chỉ mở quyền xem

    officer_page.get_by_role("button", name="Chia sẻ", exact=True).click()
    officer_page.get_by_role("dialog").get_by_role("radio", name="Riêng tư").click()
    officer_page.get_by_role("button", name="Lưu thay đổi").click()
    expect(officer_page.get_by_role("dialog")).to_have_count(0)
    other.goto(f"{BASE_URL}/documents/{doc_id}")
    expect(other.get_by_role("alert")).to_be_visible()


def test_highlight_and_versions(officer_page: Page, tmp_path, uniq):
    need(officer_page, "highlight", "versions")
    page = officer_page
    doc_id = upload_and_wait(page, make_pdf(tmp_path / "h.pdf", [f"Từ khóa nổi bật {uniq} ở đây"]), f"HL {uniq}")
    page.goto(f"{BASE_URL}/documents/{doc_id}/pages/1?q={uniq}")
    expect(page.get_by_test_id("highlight-box")).to_have_count(1)
    page.goto(f"{BASE_URL}/documents/{doc_id}/pages/1/edit")
    editor = page.get_by_label("Nội dung OCR")
    editor.fill(editor.input_value().replace("nổi bật", "đã đổi"))
    page.get_by_role("button", name="Lưu phiên bản mới").click()
    page.goto(f"{BASE_URL}/documents/{doc_id}/pages/1/edit")
    page.get_by_label("Từ phiên bản").select_option(index=0)
    # Diff theo từ: "nổi bật" -> "đã đổi" hiển thị từng từ bị xóa/thêm
    expect(page.locator("del", has_text="bật")).to_be_visible()
    expect(page.locator("ins", has_text="đổi")).to_be_visible()


def test_import_zip_report(officer_page: Page, tmp_path, uniq):
    need(officer_page, "imports")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.write(make_pdf(tmp_path / "a.pdf", [f"Lô {uniq} file a"]), "a.pdf")
        zf.writestr("../evil.pdf", b"x")
    archive = tmp_path / f"lo-{uniq}.zip"
    archive.write_bytes(buf.getvalue())
    page = officer_page
    page.goto(f"{BASE_URL}/imports")
    page.locator("input[name=files]").set_input_files(str(archive))
    page.get_by_label("Danh mục").select_option(label="Hợp đồng")
    page.get_by_role("button", name="Bắt đầu nhập").click()
    expect(page.get_by_text("1/2 file đã nhập")).to_be_visible(timeout=60_000)
    expect(page.get_by_text("UNSAFE_PATH")).to_be_visible()


def test_rollback_from_audit(page: Page, tmp_path, uniq):
    login(page, ADMIN)
    need(page, "rollback")
    page.goto(f"{BASE_URL}/admin/categories")
    page.get_by_role("button", name="Tạo danh mục").click()
    page.get_by_label("Tên").fill(f"Tạm {uniq}")
    page.get_by_label("Mã").fill(f"TAM-{uniq}".upper())
    page.get_by_role("button", name="Lưu").click()
    row = page.get_by_role("row", name=f"Tạm {uniq}")
    row.get_by_role("button", name="Ngừng dùng").click()
    # Chờ nút đổi thành "Dùng lại" (= PATCH xong). Chờ chữ "Ngừng dùng" thì khớp ngay chính cái nút vừa bấm.
    expect(row.get_by_role("button", name="Dùng lại")).to_be_visible()
    page.goto(f"{BASE_URL}/admin/audit")
    page.get_by_placeholder("Hành động (vd. edit_ocr)").fill("deactivate_category")
    # Bảng giữ dữ liệu cũ (placeholderData) trong lúc lọc: chờ dòng đầu là kết quả lọc rồi mới bấm,
    # nếu không .first có thể là nút Khôi phục của một dòng nhật ký khác.
    first_row = page.locator("tbody tr").first
    expect(first_row.locator("code")).to_have_text("deactivate_category")
    first_row.get_by_role("button", name="Khôi phục").click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_role("button", name="Khôi phục").click()
    expect(dialog).to_be_hidden()  # hộp thoại đóng khi POST rollback thành công; goto sớm hơn có thể hủy request
    page.goto(f"{BASE_URL}/admin/categories")
    expect(page.get_by_role("row", name=f"Tạm {uniq}").get_by_text("Đang dùng")).to_be_visible()
