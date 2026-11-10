# Tóm tắt trạng thái ProjectB (baseline SDD v0.13) — cập nhật 10/11/2026

Trạng thái chung: **MVP + toàn bộ P2 (P2-01…P2-09) + phân hệ quản trị/tài khoản (FR-09…FR-13) + các bổ sung sau
demo 09/11 (SDD v0.13: FR-14…FR-18, D-12, D-13) đã hiện thực**; đặc tả v0.13 khớp với code; CI xanh trên mọi PR
(#1–#37). Việc còn lại chủ yếu cần **dữ liệu thật** để đo chất lượng và thử gửi email thật qua Gmail (mục 4).

## 1. Đã hoàn thành

| Hạng mục | Nội dung | Bằng chứng |
|---|---|---|
| Backend MVP | 9 module lõi (auth, users, categories, documents, jobs, ocr, search, dashboard, audit), 4 lớp mỗi module; v0.13 thêm 3 module lõi settings, analytics, sharing | test API/unit trong `backend/tests/` |
| Backend P2 | P2-01…P2-09 (10 module/file bổ sung), cờ `FEATURES_ENABLED`, router tắt → 404 | test_p2_*.py |
| Quản trị và tài khoản | FR-09 tài khoản của tôi, FR-10 phòng ban, FR-11 hàng đợi xử lý, FR-12 vai trò Người dùng thông thường + nhóm quyền, FR-13 chia sẻ | test_v07_*.py, test_v08_sharing.py |
| Quyền sửa (D-11) | Policy ở `documents/domain/policies.py`, `DocumentOut.permissions` + `edit_lock_reason`, action `withdraw`/`return` | test_v012_permissions.py (ma trận 288 trường hợp); e2e test_review_locks_editing_d11 |
| Điểm mở rộng | ModuleSpec + registry, job kind registry (`jobs.run`), event sau commit, port OcrEngine/Storage/Notifier/EmailSender (v0.13), hook trước khi gửi duyệt (`shared/submit_hooks`, v0.13), API truy vấn công khai, UI registry + slot | import-linter 5 contract KEPT; ESLint chặn import sai ranh giới |
| CSDL | Alembic `0001_core` + `0101…0106` (mỗi module P2 một revision) + `0107` vai trò Người dùng thông thường, `0108` chia sẻ, `0109` nguồn danh mục, `0110` rút lại/trả lại, `0111…0115` bổ sung v0.13 (bản cứng/Kho chung, cấu hình hệ thống, thống kê theo ngày, tài liệu đi kèm, link chia sẻ ra ngoài); trigger audit append-only (cho phép ON DELETE SET NULL) | `alembic check` sạch trên SQLite và PostgreSQL; upgrade/downgrade/upgrade (CI mỗi PR) |
| Đặc tả | `document/` v0.13: SDD (file 0), Đặc tả đề tài (file 2), Use Case/Sequence/ERD (file 3, vẽ lại Hình 1, Hình 8, thêm Hình 2b), script CSDL (file 4, sinh từ Alembic `0001…0115`, 21 bảng); file 1 (khảo sát) không đánh số phiên bản | script file 4 chạy sạch trên PostgreSQL 18 |
| Frontend | React 19 + TS + Vite 8, React Router 7, TanStack Query 5, CSS Modules, Chart.js; 18 feature (8 lõi + 10 P2, lazy); types sinh từ OpenAPI; v0.13 thêm trang Thống kê, Cấu hình, tab Tài liệu đi kèm, hộp thoại Chia sẻ ra ngoài, trang công khai `/s/:token` | 75 test Vitest (21 file); tsc/eslint/prettier sạch |
| Giao diện | Design token + component dùng chung; icon `lucide-react`; sidebar gom nhóm, ô tìm nhanh, avatar; đăng nhập chia đôi; dashboard theo nhóm + biểu đồ; **nền sáng/tối** (theo hệ thống / sáng / tối, lưu lựa chọn); nút theo quyền D-11 | E2E trên giao diện mới; soát ảnh chụp desktop 1440px + mobile 390px, sáng và tối |
| OCR | Chữ in: VietOCR `vgg_seq2seq` (PaddleOCR dò dòng), chia dòng dài, chống nghiêng, lọc ký tự lạ, OCR vùng ảnh trong PDF có lớp chữ, dừng OCR. Chữ viết tay: VietOCR `vgg_transformer` trên hàng đợi `ocr_hw`, chia dòng, dùng chung model dò dòng | scan thật 87,7% → 98,2% (GUIDE 9.1); test_ocr_vietnamese.py, test_worker_profiles.py |
| Sao lưu (NFR-03) | Service `backup` hằng ngày (database + storage), mỗi bản tự thử khôi phục → OK/WARN/FAILED; `restore` có chốt an toàn | thử thật trên Docker; CI `compose` chạy vòng sao lưu → xóa → khôi phục |
| Hạ tầng | Nginx (SPA + /api, CSP), Dockerfile backend/frontend, compose (một `worker` nghe `default,ocr,ocr_hw` bằng image `docso-backend-hw`, xử lý cả job gửi email `EMAIL`; profile rag, tools — tools có Mailpit thử email), compose.dev, Makefile; CI 4 workflow (ma trận cờ P2); ruleset `protect-main` | — |
| Đánh giá | `backend/eval/`: CER/WER/độ chính xác ký tự, hiệu chỉnh ngưỡng, precision/recall trích xuất, top-1 phân loại, đo chữ viết tay từ bản sửa trong app | chạy với OCR thật trên scan thật (3 trang) và dữ liệu tổng hợp |
| Demo | `demo-start.cmd` / `demo-stop.cmd` (PostgreSQL riêng `.demo\`, worker, beat, API, React :8080 hoặc `-Port`) | đã chạy end-to-end với OCR thật |

### Các đợt hiện thực sau MVP + P2

| Đợt | Nội dung | PR |
|---|---|---|
| SDD v0.7 | Vai trò Người dùng thông thường + nhóm quyền (migration 0107); tài khoản của tôi, thông báo, phòng ban, thu hồi phiên; hàng đợi xử lý, cột/lọc trạng thái duyệt, nút quay lại, menu gom nhóm | #9–#12 |
| SDD v0.8 — FR-13 | Chia sẻ tài liệu đã xuất bản: Riêng tư / Nội bộ (+ phòng ban chọn thêm) / Toàn hệ thống + người đích danh; chỉ mở quyền xem (migration 0108) | #13–#15 |
| SDD v0.9, v0.10 | D-10 Danh mục gợi ý khi tải lên, danh mục hệ thống "Chưa phân loại" (migration 0109); OCR vùng ảnh nhúng trong PDF; văn bản ký số; dừng OCR; model OCR nhanh (scan 17 trang: 1241 s → 67 s) | #16–#19 |
| SDD v0.11 | VietOCR cho chữ in, lọc ký tự lạ, sửa chống nghiêng nhân đôi góc: scan thật 87,7% → 98,2% | #20, #21 |
| P2-08 | Nhập hàng loạt có Danh mục gợi ý; `metadata.csv` thêm `category`, `document_code`, nút Tải file mẫu | #22 |
| SDD v0.12 — D-11 | Quyền sửa theo người tải lên và trạng thái duyệt; Rút lại, Trả lại (migration 0110); giao diện nút theo quyền | #24, #25 |
| P2-03 vận hành | Worker chính nhận cả `ocr_hw` (bỏ `worker-hw` / `-Hw` — trước đây quên `-Hw` thì job chữ viết tay chờ mãi); engine chữ viết tay chia dòng, dùng chung model dò dòng (45–100 → 22–27 s/trang); Nhập hàng loạt có ô Tài liệu viết tay | #26 |
| FR-11 | Hàng đợi xử lý không hiện job của tài liệu trong thùng rác (trước đây hiện và cho Chạy lại → lỗi không tìm thấy tài liệu); khôi phục thì job hiện lại | #27 |
| SDD v0.13 (đặc tả) | Bổ sung sau demo 09/11: FR-14…FR-18, D-12, D-13; UC-30…UC-33; ERD 21 bảng; vẽ lại Hình 1, Hình 8, thêm Hình 2b | #29 |
| FR-06 | Tìm theo nội dung khớp cả tên tài liệu (không dấu), nhãn "Khớp tên tài liệu" | #30 |
| D-12 | Gửi duyệt khai báo bản cứng (kho/kệ hoặc Kho chung), chặn mượn bản nháp và Kho chung, sửa vị trí sau xuất bản (migration 0111) | #31 |
| FR-14 | Admin cấu hình thời gian lưu thùng rác (1–365 ngày) và audit log (180–3650 ngày), beat dọn audit (migration 0112) | #32 |
| FR-05 | OCR Editor mức 1: tô sáng dòng trên ảnh, dòng tin cậy thấp, tìm/thay, hoàn tác, phím tắt, chuyển trang, nháp tự lưu, xem khác biệt | #33 |
| FR-16 | Tải lên nhiều ảnh/PDF gộp thành một PDF, một job OCR | #34 |
| FR-17 | Thống kê hoạt động theo người dùng/phòng ban/thời gian, biểu đồ, xuất CSV; bảng tổng hợp theo ngày (migration 0113) | #35 |
| FR-15 | Tài liệu đi kèm, tải cả bộ (.zip), giữ file gốc khi gộp; nhập hàng loạt theo thư mục/manifest.csv (migration 0114) | #36 |
| FR-18 | Chia sẻ ra ngoài bằng link + OTP email, tối đa 24 giờ, thu hồi; trang công khai `/s/:token`; job `EMAIL` (migration 0115) | #37 |

### Kết quả kiểm thử (10/11/2026)

| Bộ | Kết quả |
|---|---|
| Backend pytest (SQLite), cờ tắt / mọi cờ bật | 491 passed, 1 skipped / 491 passed, 1 skipped |
| CI `backend`: pytest × 6 tổ hợp cờ P2 trên PostgreSQL 18 + Redis thật, migrations | xanh trên mọi PR (#1–#37) |
| CI `compose`: Docker Compose (Redis + worker + beat + Nginx) → E2E → restart Redis → sao lưu/khôi phục | xanh (chạy khi PR đổi Docker/infra) |
| Frontend Vitest | 75 passed (21 file) |
| E2E Playwright trên demo thật, mọi cờ bật (local) | 13 passed, 1 skipped (14 test: 5 MVP + 9 P2; test bỏ qua chỉ dành cho chế độ cờ tắt) |
| CI `e2e`: 3 tổ hợp cờ (MVP, P2 đợt 1, tất cả) | xanh trên mọi PR (ở chế độ MVP các test P2 tự bỏ qua) |
| ruff, ruff format, mypy, lint-imports, ESLint, tsc, Prettier | sạch |

## 2. Truy vết yêu cầu → hiện thực → test

| Mã | Backend | Frontend | Test chính |
|---|---|---|---|
| FR-01 | auth, users | features/auth, admin/UsersPage (lọc vai trò/phòng ban/trạng thái, đăng xuất mọi thiết bị) | test_auth.py (401/403/429, CSRF, Origin, khóa user thu hồi session); test_v07_admin_account.py (thu hồi phiên, đặt lại mật khẩu thu hồi phiên) |
| FR-02 | categories | admin/CategoriesPage | test_admin.py (ngừng dùng không chọn được, tài liệu cũ vẫn hiển thị) |
| FR-03 | documents/upload, file_inspector | documents/UploadPage | test_documents.py (415, 413, lỗi storage không tạo job) |
| FR-04 | jobs/runner, ocr/run_ocr, beat requeue, dừng job, OCR vùng ảnh | jobs/JobStatus (poll 2s), nút Dừng | test_ocr_jobs.py (retry không trùng, needs_review, engine lỗi, job treo); test_v010_cancel_job.py; test_v09_ocr_regions.py; test_ocr_vietnamese.py |
| FR-05 | ocr/editor | ocr/EditorPage (409 giữ draft; v0.13 mức 1: editorUtils, tô sáng dòng, tìm/thay, hoàn tác, nháp tự lưu) | test_editor_search.py; EditorForm.test.tsx, editorUtils.test.ts; e2e 409 |
| FR-06 | search (FTS PostgreSQL / substring SQLite, không dấu; v0.13 khớp cả tên, `title_match`) | search/SearchPage | test_editor_search.py (test_search_matches_title); e2e |
| FR-07 | documents/manage (lọc approval_status), purge (beat) | documents/TrashPage; DocumentsListPage (cột/lọc duyệt khi workflow bật); BackToList (quay lại giữ bộ lọc) | test_documents.py (410 quá hạn, purge giữ audit, bỏ qua job đang chạy); test_v07_jobs_documents.py; DocumentsListPage.test.tsx |
| FR-08 | dashboard, audit | dashboard (Chart.js), admin/AuditPage | test_editor_search.py, test_admin.py |
| FR-09 | users/application/account, auth/presentation/account_router (`/api/account`) | features/account (/account), notifications/NotificationsPage (/notifications) | test_v07_admin_account.py (sai mật khẩu 400, 429 kể cả khi đúng, xoay phiên + thu hồi phiên khác); AccountPage.test.tsx |
| FR-10 | users/application/departments | admin/DepartmentsPage | test_v07_admin_account.py (trùng mã 409, còn dùng 409 DEPARTMENT_IN_USE, chỉ Admin ghi) |
| FR-11 | jobs: GET /api/jobs (phạm vi qua `documents.department_document_ids` — chỉ tài liệu đang dùng, thùng rác không hiện), `is_stale` + `requeue_count` do beat ghi | jobs/JobsPage (/jobs) | test_v07_jobs_documents.py (phạm vi theo vai trò, lọc, đánh dấu job kẹt kể cả sau khi beat gửi lại); test_ocr_jobs.py::test_job_queue_hides_trashed_documents; JobsPage.test.tsx |
| FR-12 | users/domain/roles, documents/policies (VIEWER) | admin/RolesPage | test_v07_roles.py; RolesPage.test.tsx |
| FR-13 | documents/domain/policies (tách phạm vi xem / phạm vi phòng ban), queries (_view_clause, department_document_ids), application/sharing; GET/PUT /api/documents/{id}/sharing; GET /api/users/lookup; migration 0108 | documents/sharing: ShareDialog (3 chế độ, chip phòng ban, ô tìm người kiểu combobox), ShareModeBadge; nút Chia sẻ ở chi tiết; "Được chia sẻ với tôi" ở danh sách | test_v08_sharing.py: ma trận 9 người × chế độ × trạng thái xuất bản, policy khớp SQL; chia sẻ không mở quyền quản lý/duyệt/duyệt mượn; 14 mutation đều bị bắt; ShareDialog.test.tsx, DocumentDetailPage.test.tsx; e2e test_share_published_document_across_departments |
| D-10 | documents (category_source, "Chưa phân loại"), classification tự áp dụng sau OCR; imports (Danh mục gợi ý cho cả lô) | UploadPage, imports, SuggestionsTab | test_v09_auto_category.py, test_imports_auto_category.py; SuggestionsTab.test.tsx; e2e test_auto_category_on_upload, test_import_auto_category_with_metadata |
| D-11 | documents/domain/policies (EDIT, REPROCESS, DELETE, RESTORE, CANCEL_JOB, SUBMIT, WITHDRAW, SHARE), `DocumentOut.permissions`, workflow withdraw/return (migration 0110); rollback P2-09 không bị giới hạn | nút theo `permissions`, thông báo lý do khóa, Rút lại / Trả lại | test_v012_permissions.py; e2e test_review_locks_editing_d11 |
| P2-01 | workflow | workflow (nút, lịch sử, /reviews) | test_p2_workflow.py; e2e |
| P2-02 | search/highlight_module | highlight (pageOverlays) | test_p2_versions_highlight.py; HighlightOverlay.test.tsx; e2e |
| P2-03 | ocr/handwriting_module (queue ocr_hw, worker chính nhận cả ocr_hw); engine VietOCR (auto) | handwriting (uploadFields ở trang tải lên và nhập hàng loạt, reprocess) | test_p2_handwriting.py; test_worker_profiles.py; test_eval_handwriting.py (đo từ bản sửa trong app) |
| P2-04 | extraction (job EXTRACT, UNIQUE) | extraction (tab) | test_p2_extraction_classification.py |
| P2-05 | classification (job CLASSIFY, scikit-learn TF-IDF + Logistic Regression) | classification (tab) | test_p2_extraction_classification.py, test_v09_auto_category.py, SuggestionsTab.test.tsx |
| P2-06 | ocr/versions_module (difflib) | versions (editorTools) | test_p2_versions_highlight.py; e2e |
| P2-07 | borrowing + notifications (beat nhắc quá hạn) | borrowing, notifications (chuông) | test_p2_borrowing.py, test_p2_workflow.py |
| P2-08 | imports (job BULK_IMPORT, ZIP an toàn, metadata.csv) | imports | test_p2_imports.py, test_imports_auto_category.py; e2e |
| P2-09 | rollback | rollback (auditRowActions) | test_p2_rollback.py; e2e |
| FR-14 | settings (system_settings, beat purge_audit); documents đọc thời hạn thùng rác | admin/SettingsPage (/admin/settings) | test_v013_retention.py; SettingsPage.test.tsx |
| FR-15 | documents/application/attachments, domain/attachments (loại file); imports/domain/bundles (thư mục, manifest.csv) | documents/AttachmentsTab, UploadPage, imports | test_v013_attachments.py, test_v013_import_bundles.py; AttachmentsTab.test.tsx |
| FR-16 | documents/upload (upload_merged, merge_files), infrastructure/merge (PyMuPDF) | documents/UploadPage (chọn nhiều, sắp thứ tự) | test_v013_merge_upload.py; UploadPage.test.tsx |
| FR-17 | analytics (daily_activity_stats, beat refresh_activity_stats, export CSV) | admin/AnalyticsPage (/admin/analytics, Chart.js) | test_v013_analytics.py; AnalyticsPage.test.tsx |
| FR-18 | sharing (share_links, OTP + phiên xem trong session store, job EMAIL), shared/email (EmailSender SMTP) | documents/sharing/ExternalShareDialog, PublicSharePage (/s/:token) | test_v013_external_share.py; ExternalShare.test.tsx |
| D-12 | borrowing/locations (Kho chung, declare_on_submit), shared/submit_hooks; requests chặn bản nháp | workflow (hộp thoại bản cứng khi Gửi duyệt), borrowing (tab, Kho lưu trữ) | test_p2_borrowing.py (3 test D-12); components.test.tsx |
| NFR-09 | registry + cờ | registry.ts | toàn bộ test chạy lại với `TEST_FEATURES=all`; test_p2_flags.py; registry.test.ts |
| NFR-03 | `infra/backup/backup.sh` (service `backup`, `restore`) | — | CI `compose`: sao lưu → xóa tài liệu và file → khôi phục → app chạy lại |

## 3. Chênh lệch so với đặc tả

Nguyên tắc: code đã đúng thực tế thì hợp thức hóa vào đặc tả; chỗ code còn thiếu thì sửa code. Mỗi lần đổi đặc tả là
một PR riêng trước PR hiện thực.

### 3.1 Đã xử lý ở v0.6 (16/10/2026)

| # | Chênh lệch (v0.5) | Quyết định v0.6 | Ở đâu |
|---|---|---|---|
| 1 | Cột ngoài ERD ở bảng P2: `document_approvals.created_at`, `borrow_requests.purpose/created_at`, `notifications.created_at` | Đưa vào ERD | SDD §6; file 3 Hình 8 (vẽ lại), bảng thực thể |
| 2 | `notifications` gộp nội dung vào `title`, không có link | **Sửa code**: migration `0106` thêm `message`, `link_url`; workflow/borrowing truyền link; chuông React mở đúng `link_url` (thông báo cũ vẫn suy từ `type`) | SDD §6, §7.2; file 3 ERD |
| 3 | `processing_jobs.document_id` cho phép NULL | Ghi nhận (job cấp lô BULK_IMPORT) | SDD §6, P2-08; file 3 ERD, UC-23 |
| 4 | 5 endpoint + `DocumentOut.job_id` ngoài SDD | Đưa vào SDD §7 (đánh dấu `++`) | SDD §7.1, §7.2 |
| 5 | P2-01 "rejected → draft" | Chốt `rejected → pending_review` bằng `submit` (bỏ bước draft trung gian) | SDD P2-01; file 3 UC-13, UC-14 |
| 6 | P2-05 scikit-learn | Ghi vào tiêu chí (TF-IDF + Logistic Regression, `CLASSIFY_MIN_SCORE` 0,3 cho gợi ý cao nhất) | SDD P2-05; file 2 §3; file 3 UC-22 |
| 7 | Giới hạn highlight P2-02 | Ghi là giới hạn chấp nhận | SDD P2-02; file 3 UC-19 |
| 8 | D-02 còn mở | **Chốt**: chủ sở hữu + cùng phòng ban; Admin xem tất cả; xuất bản không mở rộng phạm vi (v0.8 bổ sung chia sẻ FR-13) | SDD §3, §11; file 2 §6; file 3 UC-05a, UC-15 |
| 9 | Dashboard chỉ đếm job OCR | Ghi vào FR-08 | SDD FR-08; file 3 UC-07 |
| 10 | Phạm vi rollback P2-09 | Ghi rõ loại hỗ trợ + 422 `ROLLBACK_NOT_SUPPORTED` + API xem trước | SDD P2-09, §7.2; file 3 UC-08b |
| + | `documents.department_id` có trong DB nhưng ERD v0.5 không vẽ | Vẽ lên ERD (căn cứ của D-02) | file 3 Hình 8 |

Script CSDL v0.5 thực ra chỉ có phần MVP (revision 0001); từ v0.6 script sinh lại từ Alembic (v0.13: `0001…0115`, 21 bảng).

### 3.2 Quyết định chốt sau v0.6

| Mã | Quyết định | Phiên bản |
|---|---|---|
| D-07, D-08 | Vai trò Người dùng thông thường (chỉ xem tài liệu đã xuất bản của phòng ban mình); nhóm quyền cố định theo vai trò | v0.7 |
| D-09 | Chia sẻ chỉ mở quyền xem; duyệt, xuất bản, duyệt mượn giới hạn ở Kiểm duyệt viên phòng ban của tài liệu | v0.8 |
| D-10 | Mặc định Danh mục gợi ý khi tải lên; "Chưa phân loại" là danh mục hệ thống, không chọn tay, không bao giờ được gợi ý | v0.9 |
| D-11 | Nháp/Bị từ chối: người tải lên sửa; Chờ duyệt/Đã duyệt/Đã hủy xuất bản: Kiểm duyệt viên phòng ban hoặc Admin sửa, không chạy lại OCR; Đã xuất bản: không ai sửa; Khôi phục từ nhật ký (P2-09) không bị giới hạn | v0.12 |
| FR-11 | Hàng đợi xử lý không hiện job của tài liệu trong thùng rác (trước ghi "kể cả trong thùng rác") | v0.12 (sửa 02/11) |
| D-12 | Gửi duyệt hỏi bản cứng (có → kho/kệ; không → Kho chung, không mượn được); chỉ mượn tài liệu đã xuất bản; chủ sở hữu, Kiểm duyệt viên, Admin sửa vị trí sau xuất bản | v0.13 |
| D-13 | Chia sẻ ra ngoài: chỉ tài liệu đã xuất bản, link ≤ 24 giờ, OTP gửi tới email người nhận, thu hồi được; email qua SMTP (Gmail app password) | v0.13 |

Khác đặc tả có chủ đích ở v0.13 (ghi trong PR #36): quy ước thư mục khi nhập hàng loạt chỉ áp dụng cho thư mục có
`dinh-kem/` hoặc `main.*`; thư mục thường vẫn nhập từng file như trước để không phá các lô ZIP đang dùng.

## 4. Việc còn lại

| Việc | Cần gì | Công cụ có sẵn |
|---|---|---|
| **NFR-08** báo cáo độ chính xác OCR chính thức | tập test thật: scan rõ, scan khó, chữ viết tay, ≥ 30 trang mỗi loại (tách tập phát triển để hiệu chỉnh ngưỡng) | `eval/ocr_eval.py`. Hiện có: scan thật 3 trang 98,2% (`vgg_seq2seq`) / 99,1% (`vgg_transformer`); trang tổng hợp 99%+ (GUIDE 9.1) |
| Hiệu chỉnh `NEEDS_REVIEW_THRESHOLD` | ≥ 30 trang thật (độ tin cậy VietOCR ~86, thấp hơn PaddleOCR dù đúng hơn) | `eval/calibrate_threshold.py` |
| **P2-03** kiểm chứng chữ viết tay > 70% (D-06) | mẫu chữ viết tay thật: tải lên (tick "Tài liệu viết tay"), sửa text cho đúng trong OCR Editor | VietOCR đã sẵn trên demo và Docker (GUIDE 4.3); đo bằng `eval/handwriting_from_app.py` |
| **P2-04, P2-05** precision/recall trích xuất, top-1 phân loại | tập mẫu có nhãn | `eval/extraction_eval.py`, `eval/classification_eval.py` |
| **D-01** chốt giới hạn file/trang | đo trên máy triển khai | biến `MAX_UPLOAD_MB` (25), `MAX_PAGES` (100), `MAX_MERGE_FILES` (20), `MAX_ATTACHMENTS` (20) |
| **FR-18** thử gửi email thật | tài khoản Gmail + app password trong `.env` (GUIDE 4.4); `PUBLIC_BASE_URL` trỏ đúng địa chỉ người nhận mở được | đã test bằng sender giả; Mailpit cho thử local |
| Email chờ OCR | job `EMAIL` dùng chung worker với OCR nên thư/OTP có thể đến chậm khi đang OCR tài liệu dài | tách hàng đợi `mail` + worker nhẹ nếu cần |
| Ngưỡng "dòng tin cậy thấp" trong OCR Editor | cố định 0,8 — cần dữ liệu thật để chỉnh | `editorUtils.ts` (`LOW_SCORE`) |
| Bắt buộc CI xanh trước khi merge | sửa ruleset (GUIDE 7.1) — đến 02/11 vẫn chưa bật | không còn test chập chờn đã biết |
| Chép bản sao lưu ra ngoài máy | tùy nơi triển khai (ổ ngoài, cloud) | `BACKUP_DIR` (GUIDE 6.4) |
| CD (tự triển khai) | server | chưa làm |

## 5. Đã kiểm chứng khi chạy thật

- **Redis/Docker (06/10/2026):** Smart App Control đã tắt. Chạy Redis + worker + beat trong Docker
  (`docker-start.cmd`, GUIDE mục 6) và gia cố cho Redis thật: tập session của user được gia hạn cùng session
  (trước đây khóa tài khoản có thể không thu hồi được session), bộ đếm rate limit INCR+EXPIRE NX nguyên tử,
  client Redis có timeout + API trả 503 khi mất Redis, visibility timeout broker ≥ 2×JOB_STALE_SECONDS,
  gửi job thử lại ngắn rồi báo QUEUE_UNAVAILABLE, worker `-P solo`, healthcheck/depends_on compose sửa lại,
  volume model OCR đúng quyền, `.dockerignore` gốc. CI: test backend trên Redis thật (`TEST_REDIS_URL`) và
  workflow `compose.yml` (build → up → E2E qua Nginx).
  **Đã chạy thật trên Docker Desktop 4.94 / WSL2:** build + up lần đầu thành công; smoke test, E2E qua Nginx; backend
  trên Redis thật. Thử sự cố:

  | Tình huống | Kết quả |
  |---|---|
  | Restart Redis | session còn nguyên (AOF) |
  | Redis treo (pause) / dừng hẳn | API trả 503 `SERVICE_UNAVAILABLE` sau ~4s / ~8s (tra DNS), tự hồi phục |
  | Worker tắt khi upload | job chờ trong Redis, xử lý ngay khi worker lên |
  | Kill worker giữa lúc OCR 8 trang | worker lên lại nhận lại job bỏ dở, xong sau 88s, attempt=2, không trùng kết quả |
  | Tạo lại container api (deploy) | Nginx nối lại sau ~2s |

  Lỗi tìm ra nhờ chạy thật và đã sửa: (1) job `processing` của worker chết chỉ được nhận lại sau visibility
  timeout Redis (~1 giờ) → worker khởi động nhận lại job dở của chính host (`release_orphaned_jobs`) + beat gửi
  lại job processing quá `JOB_STALE_SECONDS`; (2) Nginx giữ IP cũ của api → 502 sau mỗi lần deploy → `resolver`
  Docker; (3) healthcheck web luôn unhealthy (localhost → IPv6); (4) Redis treo làm request chờ 10s → timeout 2s.
  Lưu ý: cookie session `Secure` ở production — trình duyệt chấp nhận qua http://127.0.0.1, công cụ như httpx thì không.
  Demo mục 3 vẫn dùng session bộ nhớ + broker PostgreSQL (không cần Docker).
- **CI (từ 10/10/2026):** repo github.com/mowazee/ProjectB_TLCN (public từ 13/10); 4 workflow. Lần chạy đầu phát
  hiện và đã sửa: `.gitignore` bỏ sót `backend/app/shared/storage/`; phiên bản thư viện CI ≠ máy dev (→
  `backend/constraints.txt`); health không nhận HEAD; openapi.json không ổn định; e2e dùng cờ "all"; bandit assert.
  Ruleset `protect-main` chặn push thẳng/force-push vào `main`, bắt PR + 1 approve, chỉ squash merge (GUIDE 7.1).
- **Test chập chờn (sửa ở PR #4):** `App.test.tsx` do sau đăng nhập có hai lần điều hướng chồng nhau làm trang đích
  mount 2 lần (lỗi app, test giờ đếm số lần mount); E2E `test_rollback_from_audit` do ba race trong test.
- **Sao lưu/khôi phục (16/10/2026):** thử thật trên project Docker tách biệt: sao lưu OK, phát hiện thiếu file (WARN),
  từ chối khi thiếu `--yes`/còn kết nối, khôi phục sau sự cố từ bản cũ nhất, lịch hằng ngày đúng giờ. Lần thử đầu bắt
  được 2 lỗi của script (biến hàm sh toàn cục làm khôi phục nhầm bản; dọn bản cũ xóa mất bản đang cần) — đã sửa.
- **Giao diện (16–17/10/2026):** sửa kèm nút menu mobile hiện trên desktop và cột thao tác lệch hàng bảng. Nền tối:
  màu biểu đồ kiểm tra bằng validator trên đúng màu nền thẻ của app (sáng `#ffffff`, tối `#111827`); trang scan giữ nền
  trắng ở cả hai chế độ (là nội dung); script đặt giao diện là file tĩnh `theme-init.js` vì CSP của Nginx chặn script inline.
- **OCR tiếng Việt (21/10/2026):** model PaddleOCR `latin_PP-OCRv5_mobile_rec` không có chữ có dấu chồng ("CỘNG HÒA XÃ
  HỘI" → "CNG HOÀ X HI" mà độ tin cậy vẫn ~97%) → chuyển chữ in sang VietOCR; khi đo phát hiện bước chống nghiêng xoay
  cùng chiều làm góc nghiêng nhân đôi — sửa riêng lỗi này đưa scan thật từ 92% lên 98% (GUIDE mục 9).
- **Chữ viết tay trên Docker (02/11/2026):** job chữ viết tay đứng "Đang chờ" vì bản Docker cũ cần `-Hw` mới bật
  `worker-hw` → worker chính nhận luôn `ocr_hw` (#26). Đo engine chữ viết tay trên trang chữ in: 45–100 s/trang → 22–27
  s/trang, độ chính xác 98,6% → 99,1%; worker nạp cả hai engine tốn thêm ~0,9 GB RAM.
- **Hàng đợi xử lý (02/11/2026):** tài liệu đã xóa vẫn hiện trong Hàng đợi và cho Chạy lại OCR → báo lỗi không tìm thấy
  tài liệu → chỉ hiện job của tài liệu đang dùng (#27). Dọn dữ liệu thử trên Docker: 3 danh mục tạm `TAM-*` và 5 tài
  liệu trong thùng rác đi kèm (giữ nhật ký).
- **Build Docker (02/11/2026):** `-Build` đứng lâu ở bước `pip install` vì cache build bị Docker tự dọn và mạng tới PyPI
  chậm (~240–480 kB/s; PyTorch tải nhanh). `ARG WITH_HW` trong `backend/Dockerfile` khai báo trước bước pip chung làm
  image api/beat và worker tải thư viện hai lần song song → dời xuống sau bước đó (GUIDE 6.2).

### Lịch sử PR

| PR | Ngày merge | Nội dung |
|---|---|---|
| #1 | 09/10 | CI: sửa các lỗi của lần chạy đầu |
| #2 | 16/10 | Hướng dẫn quy trình Git, GitHub và CI |
| #3 | 16/10 | Đặc tả v0.6: xử lý 10 chênh lệch so với hiện thực |
| #4 | 16/10 | NFR-03 sao lưu/khôi phục tự động + sửa 2 test chập chờn |
| #5 | 16/10 | Thiết kế lại giao diện, thêm icon (lucide-react) |
| #6 | 16/10 | Giao diện nền tối + cập nhật tài liệu |
| #7 | 17/10 | P2-03: OCR chữ viết tay bằng VietOCR + đo độ chính xác từ app |
| #8 | 18/10 | GUIDE mục 9 — kế hoạch cải thiện OCR tiếng Việt có dấu |
| #9 | 18/10 | Đặc tả v0.7: phân hệ quản trị, tài khoản, vai trò Người dùng thông thường |
| #10 | 18/10 | FR-12: vai trò Người dùng thông thường, trang Nhóm quyền |
| #11 | 18/10 | FR-09, FR-10: tài khoản của tôi, thông báo, phòng ban, thu hồi phiên |
| #12 | 18/10 | FR-11, FR-07: hàng đợi xử lý, trạng thái duyệt, nút quay lại, menu gom nhóm |
| #13 | 18/10 | Đặc tả v0.8: chia sẻ tài liệu đã xuất bản (FR-13) |
| #14 | 18/10 | FR-13 backend (migration 0108) |
| #15 | 18/10 | FR-13 giao diện (hộp thoại Chia sẻ, Được chia sẻ với tôi) |
| #16 | 21/10 | Đặc tả v0.9: danh mục tự động khi tải lên (D-10), OCR vùng ảnh |
| #17 | 21/10 | FR-04: OCR vùng ảnh, văn bản ký số, dừng OCR, model OCR nhanh (SDD v0.10) |
| #18 | 21/10 | D-10: danh mục tự động khi tải lên, tab Gợi ý danh mục thiết kế lại |
| #19 | 21/10 | E2E không sinh danh mục TAM-xxxxx; sửa tab Gợi ý danh mục khi job xong quá nhanh |
| #20 | 21/10 | OCR: đọc đúng dấu tiếng Việt cho chữ in (VietOCR, lọc ký tự lạ, sửa chống nghiêng) |
| #21 | 21/10 | Đặc tả v0.11: OCR chữ in tiếng Việt bằng VietOCR |
| #22 | 23/10 | P2-08: nhập hàng loạt có Danh mục gợi ý; metadata.csv thêm category, document_code |
| #23 | 23/10 | Demo: mật khẩu admin không lấy nhầm `DEMO_ADMIN_PASSWORD` của Docker |
| #24 | 26/10 | Đặc tả v0.12: D-11 quyền sửa; nhập hàng loạt có Danh mục gợi ý |
| #25 | 26/10 | D-11: quyền sửa theo chủ sở hữu và trạng thái duyệt; Rút lại, Trả lại |
| #26 | 02/11 | P2-03: worker chính nhận `ocr_hw`, bỏ `-Hw`; engine chữ viết tay chia dòng, dùng chung model dò dòng |
| #27 | 02/11 | FR-11: Hàng đợi xử lý không hiện job của tài liệu trong thùng rác |
| #28 | 02/11 | Cập nhật README, GUIDE, SUMMARY; Dockerfile dùng chung lớp thư viện cho api và worker |
| #29 | 10/11 | Đặc tả v0.13: FR-14…FR-18, D-12, D-13; vẽ lại Hình 1, Hình 8, thêm Hình 2b |
| #30 | 10/11 | FR-06: tìm theo nội dung khớp cả tên tài liệu |
| #31 | 10/11 | D-12: khai báo bản cứng khi gửi duyệt, Kho chung, chặn mượn bản nháp |
| #32 | 10/11 | FR-14: cấu hình thời gian lưu thùng rác và audit log |
| #33 | 10/11 | FR-05: OCR Editor mức 1 |
| #34 | 10/11 | FR-16: tải lên nhiều ảnh/PDF gộp thành một tài liệu |
| #35 | 10/11 | FR-17: thống kê hoạt động theo người dùng, phòng ban, thời gian |
| #36 | 10/11 | FR-15: tài liệu đi kèm, tải cả bộ, nhập hàng loạt theo bộ hồ sơ |
| #37 | 10/11 | FR-18: chia sẻ ra ngoài bằng link + OTP email |
