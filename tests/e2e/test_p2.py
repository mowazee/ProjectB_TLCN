"""Luồng P2 end to end; mỗi test tự bỏ qua khi cờ tương ứng đang tắt (NFR-09, e2e.yml matrix)."""

import io
import re
import zipfile

import pytest
from playwright.sync_api import Page, expect

from conftest import (
    ADMIN,
    APPROVER,
    BASE_URL,
    OTHER_DEPT_OFFICER,
    choose_category,
    features,
    login,
    make_pdf,
    upload_and_wait,
)


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
    doc_id = upload_and_wait(
        officer_page, make_pdf(tmp_path / "w.pdf", [f"Quyết định {uniq} ban hành"]), f"Duyệt {uniq}"
    )
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
        # nội dung khớp nhãn Hợp đồng: tài liệu nguồn user là mẫu huấn luyện phân loại trên dữ liệu demo
        zf.write(make_pdf(tmp_path / "a.pdf", [f"Hợp đồng mua bán lô {uniq}, bên A và bên B"]), "a.pdf")
        zf.writestr("../evil.pdf", b"x")
    archive = tmp_path / f"lo-{uniq}.zip"
    archive.write_bytes(buf.getvalue())
    page = officer_page
    page.goto(f"{BASE_URL}/imports")
    page.locator("input[name=files]").set_input_files(str(archive))
    choose_category(page, "Hợp đồng")
    page.get_by_role("button", name="Bắt đầu nhập").click()
    expect(page.get_by_text("1/2 file đã nhập")).to_be_visible(timeout=60_000)
    expect(page.get_by_text("UNSAFE_PATH")).to_be_visible()


def test_import_auto_category_with_metadata(officer_page: Page, tmp_path, uniq):
    """P2-08 + D-10: lô Danh mục gợi ý; metadata.csv ghi đè danh mục (mã) và số hiệu của một file."""
    need(officer_page, "imports", "classification")
    contract = [  # cùng nội dung test_auto_category_on_upload: đủ tin cậy để tự áp dụng Hợp đồng
        "HỢP ĐỒNG KINH TẾ MUA BÁN HÀNG HÓA",
        f"Số: {uniq}/2026/HĐKT",
        "Bên A (bên bán) và Bên B (bên mua) thỏa thuận ký kết hợp đồng mua bán",
        "Giá trị hợp đồng: 150.000.000 đồng; thanh toán bằng chuyển khoản",
        "Hợp đồng kinh tế có hiệu lực kể từ ngày ký; dịch vụ bảo hành 12 tháng",
    ]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.write(make_pdf(tmp_path / "a.pdf", contract), "a.pdf")
        zf.write(make_pdf(tmp_path / "b.pdf", [f"Biên bản {uniq}"]), "b.pdf")
        zf.writestr(
            "metadata.csv", f"file_name,title,category,document_code\nb.pdf,Biên bản {uniq},BAO-CAO,{uniq}/BB\n"
        )
    archive = tmp_path / f"auto-{uniq}.zip"
    archive.write_bytes(buf.getvalue())
    page = officer_page
    page.goto(f"{BASE_URL}/imports")
    expect(page.get_by_role("radio", name=re.compile("Danh mục gợi ý"))).to_have_attribute("aria-checked", "true")
    page.locator("input[name=files]").set_input_files(str(archive))
    page.get_by_role("button", name="Bắt đầu nhập").click()
    expect(page.get_by_text("2/2 file đã nhập")).to_be_visible(timeout=60_000)
    row_b = page.get_by_role("row").filter(has=page.get_by_role("cell", name=re.compile(r"b\.pdf$")))
    expect(row_b).to_contain_text("Người dùng chọn")
    expect(row_b).to_contain_text("Báo cáo - Biên bản")
    row_a = page.get_by_role("row").filter(has=page.get_by_role("cell", name=re.compile(r"a\.pdf$")))
    expect(row_a).to_contain_text("Tự động", timeout=120_000)  # OCR + tự phân loại xong, báo cáo tự cập nhật


TAM = ("TAM", "Tạm")  # danh mục dùng lại mọi lần chạy: không sinh thêm danh mục trên dữ liệu demo


def test_rollback_from_audit(page: Page):
    login(page, ADMIN)
    need(page, "rollback")
    page.goto(f"{BASE_URL}/admin/categories")
    expect(page.get_by_role("button", name="Tạo danh mục")).to_be_visible()
    row = page.get_by_role("row").filter(has=page.get_by_role("cell", name=TAM[0], exact=True))
    page.locator("tbody tr").first.wait_for()
    if not row.count():  # CSDL mới (CI): tạo lần đầu
        page.get_by_role("button", name="Tạo danh mục").click()
        page.get_by_label("Tên").fill(TAM[1])
        page.get_by_label("Mã").fill(TAM[0])
        page.get_by_role("button", name="Lưu").click()
    elif row.get_by_role("button", name="Dùng lại").count():  # lần chạy trước dừng giữa chừng
        row.get_by_role("button", name="Dùng lại").click()
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
    expect(row.get_by_text("Đang dùng")).to_be_visible()


def test_auto_category_on_upload(officer_page: Page, tmp_path, uniq):
    """D-10: tải lên với Danh mục gợi ý -> OCR -> tự áp dụng; Áp dụng gợi ý khác thì khối đang áp dụng đổi theo."""
    need(officer_page, "classification")
    page = officer_page
    page.goto(f"{BASE_URL}/documents/new")
    expect(page.get_by_role("radio", name=re.compile("Danh mục gợi ý"))).to_have_attribute("aria-checked", "true")
    lines = [
        "HỢP ĐỒNG KINH TẾ MUA BÁN HÀNG HÓA",
        f"Số: {uniq}/2026/HĐKT",
        "Bên A (bên bán) và Bên B (bên mua) thỏa thuận ký kết hợp đồng mua bán",
        "Giá trị hợp đồng: 150.000.000 đồng; thanh toán bằng chuyển khoản",
        "Hợp đồng kinh tế có hiệu lực kể từ ngày ký; dịch vụ bảo hành 12 tháng",
    ]
    page.locator("input[name=file]").set_input_files(make_pdf(tmp_path / "auto.pdf", lines))
    page.get_by_label("Tiêu đề").fill(f"HĐ tự phân loại {uniq}")
    page.get_by_role("button", name="Tải lên").click()
    page.get_by_role("link", name="Mở tài liệu").click()
    page.get_by_role("tab", name="Gợi ý danh mục").click()
    summary = page.get_by_role("region", name="Danh mục đang áp dụng")
    expect(summary.get_by_text("Tự động phân loại")).to_be_visible(timeout=120_000)
    rows = page.get_by_role("listitem")
    auto_name = rows.filter(has_text="Đang áp dụng").locator("strong").inner_text()
    expect(summary.get_by_text(auto_name, exact=True)).to_be_visible()  # khối trên và dòng đang áp dụng khớp nhau

    other = rows.filter(has=page.get_by_role("button", name="Áp dụng")).first
    name = other.locator("strong").inner_text()
    other.get_by_role("button", name="Áp dụng").click()
    expect(summary.get_by_text(name, exact=True)).to_be_visible()
    expect(summary.get_by_text("Người dùng chọn")).to_be_visible()
    expect(page.get_by_text("Đang áp dụng", exact=True)).to_have_count(1)
    expect(rows.filter(has_text=name)).to_contain_text("Đang áp dụng")

    # trả về nhãn đúng: tài liệu E2E thành mẫu huấn luyện (nguồn user) cho lần chạy sau trên cùng dữ liệu demo
    if name != "Hợp đồng":
        rows.filter(has_text="Hợp đồng").get_by_role("button", name="Áp dụng").click()
        expect(summary.get_by_text("Hợp đồng", exact=True)).to_be_visible()


def test_review_locks_editing_d11(officer_page: Page, new_context_page, tmp_path, uniq):
    """D-11: gửi duyệt khóa sửa với người tải lên (nút mờ + lý do, Rút lại); Kiểm duyệt viên sửa, không chạy lại OCR."""
    need(officer_page, "workflow")
    page = officer_page
    doc_id = upload_and_wait(page, make_pdf(tmp_path / "d11.pdf", [f"Quyết định {uniq} về quyền sửa"]), f"D11 {uniq}")
    url = f"{BASE_URL}/documents/{doc_id}"
    expect(page.get_by_role("button", name="Sửa thông tin")).to_be_enabled()
    page.get_by_role("button", name="Gửi duyệt").click()
    page.get_by_role("dialog").get_by_role("button", name="Xác nhận").click()
    expect(page.get_by_role("note")).to_contain_text("Rút lại")
    expect(page.get_by_role("button", name=re.compile("Sửa thông tin"))).to_be_disabled()
    expect(page.get_by_role("button", name="Xóa")).to_have_count(0)

    approver = new_context_page(APPROVER)
    approver.goto(url)
    expect(approver.get_by_role("button", name="Sửa thông tin")).to_be_enabled()
    expect(approver.get_by_role("button", name="Chạy lại OCR")).to_have_count(0)

    page.get_by_role("button", name="Rút lại", exact=True).click()
    page.get_by_role("dialog").get_by_role("button", name="Xác nhận").click()
    expect(page.get_by_role("button", name="Sửa thông tin")).to_be_enabled()
    expect(page.get_by_role("note")).to_have_count(0)
