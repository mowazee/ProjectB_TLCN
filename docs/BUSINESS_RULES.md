# Quy tắc nghiệp vụ (business rules)

Gom các quy tắc nghiệp vụ đã chốt trong SDD v0.16 (mục 3, 4, 5, 11) vào một bảng để tra cứu và đối chiếu với mã nguồn.
Cột "Hiện thực" chỉ nơi quy tắc được kiểm tra ở server (React chỉ ẩn/hiện nút); cột "Test" là bằng chứng tự động.

| Mã | Quy tắc | Nguồn | Hiện thực | Test |
|---|---|---|---|---|
| BR-01 | Người dùng xem được tài liệu của mình và của phòng ban mình; Admin xem tất cả; tài liệu đã xuất bản mở rộng phạm vi xem theo chế độ chia sẻ Riêng tư / Nội bộ / Toàn hệ thống | D-02, D-09 | `documents/domain/policies.py` (`can_view`), `queries._view_clause` | test_v08_sharing.py |
| BR-02 | Người dùng thông thường (VIEWER) chỉ xem tài liệu đã xuất bản được chia sẻ tới mình | D-07, FR-12 | `policies.is_reader_only`, `can_view` | test_v07_roles.py |
| BR-03 | Quyền SỬA theo trạng thái duyệt: Nháp/Bị từ chối — chủ sở hữu; Chờ duyệt/Đã duyệt/Đã hủy xuất bản — Kiểm duyệt viên phòng ban và Admin; Đã xuất bản — không ai sửa | D-11 | `policies.can_edit`, `edit_lock_reason` | test_v012_permissions.py (ma trận 288 trường hợp) |
| BR-04 | Chạy lại OCR, xóa mềm: chủ sở hữu khi Nháp/Bị từ chối (Admin xóa mọi trạng thái); khôi phục: chủ sở hữu, Admin | D-11 | `policies.can_reprocess`, `can_delete`, `can_restore` | test_v012_permissions.py |
| BR-05 | Chuyển trạng thái duyệt chỉ theo state machine: draft → pending_review → approved/rejected; approved → published ↔ unpublished; rút lại, trả lại; sai trạng thái trả 409 | P2-01, D-11 | `workflow/domain/state_machine.py` | test_p2_workflow.py |
| BR-06 | Từ chối và trả lại bắt buộc lý do | P2-01 | `workflow/application/approvals.transition` | test_p2_workflow.py |
| BR-07 | Danh mục khi tải lên: chọn tay hoặc Danh mục gợi ý (tự áp dụng sau OCR); "Chưa phân loại" là danh mục hệ thống, không chọn tay, không được gợi ý | D-10 | `categories`, `classification` | test_v09_auto_category.py |
| BR-08 | Xóa mềm giữ trong thùng rác theo cấu hình (1–365 ngày); quá hạn xóa vĩnh viễn mọi file, dữ liệu và nhật ký của tài liệu; bỏ qua tài liệu còn job đang chạy | D-05, FR-07, FR-14, D-16 | `documents/application/purge.py` | test_documents.py, test_v013_retention.py |
| BR-09 | Nhật ký: lịch sử thay đổi của tài liệu còn tồn tại giữ vĩnh viễn; chỉ log vận hành (đăng nhập, quản trị, lượt tải/xem) dọn theo thời hạn ≥ 180 ngày | D-15, FR-14 | `audit/application/retention.py` | test_v013_retention.py |
| BR-10 | Hàng đợi xử lý giữ job đã kết thúc 30 ngày, trừ job mới nhất của mỗi tài liệu và loại job | D-16, FR-11 | `jobs/application/retention.py` | test_v014_job_retention.py |
| BR-11 | Gửi duyệt khai báo bản cứng: Có → chọn kho/kệ thật; Không → Kho chung; chỉ mượn được tài liệu đã xuất bản có bản cứng ở kho/kệ thật | D-12, P2-07 | `borrowing/application/locations.py`, `requests.py` | test_p2_borrowing.py |
| BR-12 | Hiệu lực tài liệu 4 trạng thái; bắt buộc chọn khi gửi duyệt; "đến ngày D" hết hiệu lực sau 23:59 ngày D (giờ hệ thống); ngày phải ≥ hôm nay | D-14, FR-19 | `documents/domain/validity.py`, `application/validity.py` | test_v014_validity.py |
| BR-13 | Sau khi duyệt/xuất bản chỉ Kiểm duyệt viên phòng ban và Admin đổi hiệu lực, bắt buộc lý do 5–500 ký tự | D-14 | `policies.can_change_validity`, `validity.change` | test_v014_validity.py |
| BR-14 | Tài liệu hết hiệu lực ẩn mặc định khỏi danh sách, tìm kiếm, hàng chờ; vẫn xem, mượn, chia sẻ được; nhắc chủ sở hữu một lần khi còn ≤ 7 ngày | D-14 | `queries.expired_clause`, `validity.remind_due` | test_v014_validity.py, test_v014_bulk_review.py |
| BR-15 | Duyệt/xuất bản/từ chối hàng loạt tối đa 20 tài liệu; duyệt phải xác nhận đủ 4 mục checklist; mỗi tài liệu xử lý như thao tác lẻ, lỗi tài liệu này không ảnh hưởng tài liệu khác | FR-20 | `workflow/application/approvals.bulk` | test_v014_bulk_review.py |
| BR-16 | Chia sẻ ra ngoài chỉ cho tài liệu đã xuất bản; link tối đa 24 giờ; người nhận nhập OTP gửi tới đúng email; sai 5 lần khóa 15 phút; thu hồi/hủy xuất bản làm link mất hiệu lực | D-13, FR-18 | `sharing/application/links.py` | test_v013_external_share.py |
| BR-17 | Tài liệu đi kèm theo quyền của tài liệu chính (thêm/xóa theo quyền SỬA, tải theo phạm vi xem); không OCR | FR-15 | `documents/application/attachments.py` | test_v013_attachments.py |
| BR-18 | Nhập hàng loạt chỉ theo `manifest.csv` (bắt buộc); `file_name` nhiều file phân cách `;` thì gộp một PDF, tên và tiêu đề theo `title`; file không khai báo bị bỏ qua | D-16, P2-08 | `imports/domain/bundles.py`, `application/batch.py` | test_v013_import_bundles.py, test_p2_imports.py |
| BR-19 | Sửa OCR tạo phiên bản mới; xung đột sửa đồng thời trả 409 và giữ bản nháp; sửa OCR không đổi trạng thái duyệt | FR-05 | `ocr/application/editor.py` | test_editor_search.py, e2e 409 |
| BR-20 | Tải file gốc: mọi vai trò trong phạm vi xem; mỗi lượt tải ghi nhật ký | D-08 | `documents/application/files.py` | test_documents.py |
| BR-21 | Rollback chỉ Admin, tạo thay đổi mới, không xóa lịch sử; không bị giới hạn quyền sửa theo trạng thái | P2-09, D-11 | `rollback/application/rollback.py` | test_p2_rollback.py |
| BR-22 | Mật khẩu: đổi mật khẩu cần mật khẩu hiện tại; khóa tài khoản thu hồi mọi phiên; giới hạn số lần đăng nhập sai | FR-01, FR-09 | `auth`, `users/application/account.py` | test_auth.py, test_v07_admin_account.py |
| BR-23 | Tài liệu hướng dẫn sử dụng: mọi người dùng đã đăng nhập xem và tải; chỉ Admin tải lên, sửa, xóa; file phải thuộc định dạng cho phép, nội dung khớp đuôi, không rỗng, ≤ `MAX_GUIDE_MB` | FR-21, D-17 | `guides/application/manage.py`, `guides/domain/files.py` | test_v016_guides.py, GuidePage.test.tsx |
| BR-24 | Xóa mềm tài liệu thì yêu cầu mượn đang chờ duyệt tự bị từ chối và người mượn được báo; yêu cầu đã duyệt vẫn ghi nhận trả được; khôi phục tài liệu không mở lại yêu cầu | P2-07, D-17 | `borrowing/application/requests.py` (`reject_pending_of_deleted`) | test_p2_borrowing.py |
