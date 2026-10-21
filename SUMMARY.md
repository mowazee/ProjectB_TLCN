# Tóm tắt trạng thái ProjectB (baseline SDD v0.10) — cập nhật 18/10/2026

Trạng thái chung: **MVP + toàn bộ P2 (P2-01…P2-09) + phân hệ quản trị/tài khoản SDD v0.7 (FR-09…FR-12) đã hiện thực
và chạy được end to end**; đặc tả v0.7 khớp với code; CI xanh trên mọi PR. Việc còn lại chủ yếu cần **dữ liệu thật** của nhóm để đo chất lượng (mục 4).

## 1. Đã hoàn thành

| Hạng mục | Nội dung | Bằng chứng |
|---|---|---|
| Backend MVP | 9 module lõi (auth, users, categories, documents, jobs, ocr, search, dashboard, audit), 4 lớp mỗi module | 50+ test API/unit |
| Backend P2 | P2-01…P2-09 (10 module/file bổ sung), cờ `FEATURES_ENABLED`, router tắt → 404 | test_p2_*.py |
| Điểm mở rộng | ModuleSpec + registry, job kind registry (`jobs.run`), event sau commit, port OcrEngine/Storage/Notifier, API truy vấn công khai, UI registry + slot | import-linter 5 contract KEPT; ESLint chặn import sai ranh giới |
| CSDL | Alembic `0001_core` + `0101…0106` (mỗi module P2 một revision); trigger audit append-only (cho phép ON DELETE SET NULL); CHECK `kind` mở rộng ở 0105; `notifications.message/link_url` ở 0106 | `alembic check` sạch trên SQLite và PostgreSQL; upgrade/downgrade/upgrade (CI mỗi PR) |
| Đặc tả | `document/` v0.6: SDD (file 0), Đặc tả đề tài (file 2), Use Case/Sequence/ERD (file 3, ERD vẽ lại theo migration), script CSDL (file 4, sinh từ Alembic, đủ 16 bảng) | script file 4 chạy sạch trên PostgreSQL 18 |
| Frontend | React 19 + TS + Vite 8, React Router 7, TanStack Query 5, CSS Modules, Chart.js; 15 feature (6 lõi + 9 P2, lazy); types sinh từ OpenAPI | 18 test Vitest; tsc/eslint/prettier sạch |
| Giao diện | Design token + component dùng chung; icon `lucide-react`; sidebar/header mới, ô tìm nhanh, avatar; đăng nhập chia đôi; dashboard theo nhóm + biểu đồ theo hướng dẫn trực quan hóa; **nền sáng/tối** (theo hệ thống / sáng / tối, lưu lựa chọn) | E2E 9 passed trên giao diện mới; soát ảnh chụp desktop 1440px + mobile 390px, sáng và tối |
| Sao lưu (NFR-03) | Service `backup` hằng ngày (database + storage), mỗi bản tự thử khôi phục → OK/WARN/FAILED; `restore` có chốt an toàn | thử thật trên Docker; CI `compose` chạy vòng sao lưu → xóa → khôi phục |
| Hạ tầng | Nginx (SPA + /api, CSP), Dockerfile backend/frontend, compose (profile hw, rag, tools), compose.dev, Makefile; CI 4 workflow (ma trận cờ P2); ruleset `protect-main` | — |
| Đánh giá | `backend/eval/`: CER/WER/độ chính xác ký tự, hiệu chỉnh ngưỡng, precision/recall trích xuất, top-1 phân loại | chạy thử với PaddleOCR thật trên dữ liệu tổng hợp |
| Demo | `demo-start.cmd` / `demo-stop.cmd` (PostgreSQL riêng `.demo\`, worker, beat, API, React :8080) | đã chạy end-to-end với PaddleOCR thật |

### Kết quả kiểm thử (17/10/2026)

| Bộ | Kết quả |
|---|---|
| Backend pytest (SQLite), cờ tắt / mọi cờ bật | 151 passed, 1 skipped / 151 passed, 1 skipped (21/10, thêm dừng OCR, danh mục tự động D-10) |
| CI `backend`: pytest × 6 tổ hợp cờ P2 trên PostgreSQL 18 + Redis thật, migrations | xanh trên mọi PR (#1–#5) |
| CI `compose`: Docker Compose (Redis + worker + beat + Nginx) → E2E → restart Redis → sao lưu/khôi phục | xanh (PR #4, `main` sau #4) |
| Frontend Vitest | 45 passed (21/10: thêm chọn cách gán danh mục khi tải lên, tab Gợi ý danh mục) |
| E2E Playwright trên demo thật, mọi cờ bật (local, 21/10) | 11 passed, 1 skipped (thêm luồng tải lên với Danh mục gợi ý → tự phân loại → Áp dụng gợi ý khác; test còn lại dành cho cờ tắt) |
| CI `e2e`: 3 tổ hợp cờ (MVP, P2 đợt 1, tất cả) | xanh trên mọi PR (#2–#5) |
| E2E chế độ chỉ MVP (`-Mvp`, local 05/10) | 6 passed, 4 skipped (các test P2 tự bỏ qua khi cờ tắt) |
| ruff, ruff format, mypy, lint-imports, ESLint, tsc, Prettier | sạch |

## 2. Truy vết yêu cầu → hiện thực → test

| Mã | Backend | Frontend | Test chính |
|---|---|---|---|
| FR-01 | auth, users | features/auth, admin/UsersPage (lọc vai trò/phòng ban/trạng thái, đăng xuất mọi thiết bị) | test_auth.py (401/403/429, CSRF, Origin, khóa user thu hồi session); test_v07_admin_account.py (thu hồi phiên, đặt lại mật khẩu thu hồi phiên) |
| FR-02 | categories | admin/CategoriesPage | test_admin.py (ngừng dùng không chọn được, tài liệu cũ vẫn hiển thị) |
| FR-03 | documents/upload, file_inspector | documents/UploadPage | test_documents.py (415, 413, lỗi storage không tạo job) |
| FR-04 | jobs/runner, ocr/run_ocr, beat requeue | jobs/JobStatus (poll 2s) | test_ocr_jobs.py (retry không trùng, needs_review, engine lỗi, job treo) |
| FR-05 | ocr/editor | ocr/EditorPage (409 giữ draft) | test_editor_search.py; EditorForm.test.tsx; e2e 409 |
| FR-06 | search (FTS PostgreSQL / substring SQLite, không dấu) | search/SearchPage | test_editor_search.py; e2e |
| FR-07 | documents/manage (lọc approval_status v0.7), purge (beat) | documents/TrashPage; DocumentsListPage (cột/lọc duyệt khi workflow bật); BackToList (quay lại giữ bộ lọc) | test_documents.py (410 quá hạn, purge giữ audit, bỏ qua job đang chạy); test_v07_jobs_documents.py; DocumentsListPage.test.tsx |
| FR-08 | dashboard, audit | dashboard (Chart.js), admin/AuditPage | test_editor_search.py, test_admin.py |
| FR-09 | users/application/account, auth/presentation/account_router (`/api/account`) | features/account (/account), notifications/NotificationsPage (/notifications) | test_v07_admin_account.py (sai mật khẩu 400, 429 kể cả khi đúng, xoay phiên + thu hồi phiên khác); AccountPage.test.tsx |
| FR-10 | users/application/departments | admin/DepartmentsPage | test_v07_admin_account.py (trùng mã 409, còn dùng 409 DEPARTMENT_IN_USE, chỉ Admin ghi) |
| FR-11 | jobs: GET /api/jobs (phạm vi qua documents.visible_document_ids), `is_stale` + `requeue_count` do beat ghi | jobs/JobsPage (/jobs) | test_v07_jobs_documents.py (phạm vi theo vai trò, lọc, đánh dấu job kẹt kể cả sau khi beat gửi lại); JobsPage.test.tsx |
| FR-13 | documents/domain/policies (tách phạm vi xem / phạm vi phòng ban), queries (_view_clause, department_document_ids), application/sharing; GET/PUT /api/documents/{id}/sharing; GET /api/users/lookup; migration 0108 | documents/sharing: ShareDialog (3 chế độ, chip phòng ban, ô tìm người kiểu combobox), ShareModeBadge; nút Chia sẻ ở chi tiết; "Được chia sẻ với tôi" ở danh sách | test_v08_sharing.py: ma trận 9 người × chế độ × trạng thái xuất bản, policy khớp SQL; chia sẻ không mở quyền quản lý/duyệt/duyệt mượn; jobs, thùng rác theo phòng ban; 14 mutation đều bị bắt; ShareDialog.test.tsx, DocumentDetailPage.test.tsx; e2e test_share_published_document_across_departments |
| FR-12 | users/domain/roles, documents/policies (VIEWER) | admin/RolesPage | test_v07_roles.py; RolesPage.test.tsx |
| P2-01 | workflow | workflow (nút, lịch sử, /reviews) | test_p2_workflow.py; e2e |
| P2-02 | search/highlight_module | highlight (pageOverlays) | test_p2_versions_highlight.py; HighlightOverlay.test.tsx; e2e |
| P2-03 | ocr/handwriting_module (queue ocr_hw); engine VietOCR (auto) | handwriting (uploadFields, reprocess) | test_p2_handwriting.py; test_eval_handwriting.py (đo từ bản sửa trong app) |
| P2-04 | extraction (job EXTRACT, UNIQUE) | extraction (tab) | test_p2_extraction_classification.py |
| P2-05 | classification (job CLASSIFY, scikit-learn TF-IDF + Logistic Regression) | classification (tab) | test_p2_extraction_classification.py, test_v09_auto_category.py (D-10), SuggestionsTab.test.tsx |
| P2-06 | ocr/versions_module (difflib) | versions (editorTools) | test_p2_versions_highlight.py; e2e |
| P2-07 | borrowing + notifications (beat nhắc quá hạn) | borrowing, notifications (chuông) | test_p2_borrowing.py, test_p2_workflow.py |
| P2-08 | imports (job BULK_IMPORT, ZIP an toàn) | imports | test_p2_imports.py; e2e |
| P2-09 | rollback | rollback (auditRowActions) | test_p2_rollback.py; e2e |
| NFR-09 | registry + cờ | registry.ts | toàn bộ test chạy lại với `TEST_FEATURES=all`; test_p2_flags.py; registry.test.ts |
| NFR-03 | `infra/backup/backup.sh` (service `backup`, `restore`) | — | CI `compose`: sao lưu → xóa tài liệu và file → khôi phục → app chạy lại |

## 3. Chênh lệch so với đặc tả — đã xử lý ở v0.6 (16/10/2026)

Bộ tài liệu `document/` nâng lên **v0.6** (file 0, 2, 3 và script CSDL file 4); file 1 (khảo sát) không đánh số phiên bản nên giữ nguyên.
Nguyên tắc: code đã đúng thực tế thì hợp thức hóa vào đặc tả; chỗ code còn thiếu thì sửa code.

| # | Chênh lệch (v0.5) | Quyết định v0.6 | Ở đâu |
|---|---|---|---|
| 1 | Cột ngoài ERD ở bảng P2: `document_approvals.created_at`, `borrow_requests.purpose/created_at`, `notifications.created_at` | Đưa vào ERD | SDD §6; file 3 Hình 8 (vẽ lại), bảng thực thể |
| 2 | `notifications` gộp nội dung vào `title`, không có link | **Sửa code**: migration `0106` thêm `message`, `link_url`; workflow/borrowing truyền link; chuông React mở đúng `link_url` (thông báo cũ vẫn suy từ `type`) | SDD §6, §7.2; file 3 ERD |
| 3 | `processing_jobs.document_id` cho phép NULL | Ghi nhận (job cấp lô BULK_IMPORT) | SDD §6, P2-08; file 3 ERD, UC-23 |
| 4 | 5 endpoint + `DocumentOut.job_id` ngoài SDD | Đưa vào SDD §7 (đánh dấu `++`) | SDD §7.1, §7.2 |
| 5 | P2-01 "rejected → draft" | Chốt `rejected → pending_review` bằng `submit` (bỏ bước draft trung gian) | SDD P2-01; file 3 UC-13, UC-14 (Hình 5 vốn đã đúng) |
| 6 | P2-05 scikit-learn | Đã sửa 06/10; ghi vào tiêu chí (TF-IDF + Logistic Regression, `CLASSIFY_MIN_SCORE` 0,3 cho gợi ý cao nhất) | SDD P2-05; file 2 §3; file 3 UC-22 |
| 7 | Giới hạn highlight P2-02 | Ghi là giới hạn chấp nhận | SDD P2-02; file 3 UC-19 |
| 8 | D-02 còn mở | **Chốt**: chủ sở hữu + cùng phòng ban; Admin xem tất cả; xuất bản không mở rộng phạm vi | SDD §3, §11; file 2 §6; file 3 UC-05a, UC-15 |
| 9 | Dashboard chỉ đếm job OCR | Ghi vào FR-08 | SDD FR-08; file 3 UC-07 |
| 10 | Phạm vi rollback P2-09 | Ghi rõ loại hỗ trợ + 422 `ROLLBACK_NOT_SUPPORTED` + API xem trước | SDD P2-09, §7.2; file 3 UC-08b |
| + | `documents.department_id` có trong DB nhưng ERD v0.5 không vẽ | Vẽ lên ERD (căn cứ của D-02) | file 3 Hình 8 |

Script CSDL v0.5 thực ra chỉ có phần MVP (revision 0001); bản v0.6 sinh lại từ Alembic `0001…0106`, đủ 16 bảng.

## 4. Việc còn lại

| Việc | Cần gì | Công cụ có sẵn |
|---|---|---|
| **NFR-08** báo cáo độ chính xác OCR chính thức | tập test thật: scan rõ, scan khó, chữ viết tay, ≥ 30 trang mỗi loại (tách tập phát triển để hiệu chỉnh ngưỡng) | `eval/ocr_eval.py`. Thử trên dữ liệu tổng hợp: scan rõ ~91%, scan khó ~90% (chỉ để kiểm tra quy trình); PaddleOCR `vi` hay mất dấu (WER cao) |
| **P2-03** kiểm chứng chữ viết tay > 70% | mẫu chữ viết tay thật: upload (tick "Chữ viết tay"), sửa text cho đúng trong OCR Editor | **đã cài sẵn VietOCR** (`OCR_HW_ENGINE=auto`, GUIDE 4.3); đo bằng `eval/handwriting_from_app.py`. Ảnh vẽ bằng font kiểu viết tay (chỉ kiểm tra cài đặt): VietOCR 94,4%, PaddleOCR 91,5% nhưng chèn chữ Hán và tự tin sai |
| **P2-04, P2-05** precision/recall trích xuất, top-1 phân loại | tập mẫu có nhãn | `eval/extraction_eval.py`, `eval/classification_eval.py` |
| **Hiện thực SDD v0.7** (FR-09…FR-12, mở rộng FR-01/FR-07): vai trò Người dùng thông thường, nhóm quyền, quản lý người dùng nâng cao, phòng ban, tài khoản của tôi, hàng đợi xử lý, cột trạng thái duyệt, nút quay lại, menu gom nhóm | đặc tả đã chốt (D-07, D-08) | xong: (2) vai trò & quyền + migration 0107 (#10); (3) quản trị & tài khoản (#11); (4) hàng đợi xử lý, cột/lọc trạng thái duyệt, nút quay lại, menu gom nhóm, sửa chuyển hướng sau đăng xuất (#12) |
| **Hiện thực SDD v0.8 — FR-13 Chia sẻ tài liệu đã xuất bản** (D-09): Riêng tư / Nội bộ (phòng ban của tài liệu + phòng ban chọn thêm) / Toàn hệ thống + người đích danh; chia sẻ chỉ mở quyền xem; duyệt, xuất bản, duyệt mượn giới hạn ở Kiểm duyệt viên phòng ban của tài liệu | đặc tả v0.8 (UC-29, ERD 17 bảng) | xong: (1) đặc tả v0.8 (#13); (2) backend (#14); (3) giao diện: hộp thoại Chia sẻ, nhãn chế độ, bộ lọc "Được chia sẻ với tôi", E2E |
| **Hiện thực SDD v0.9** — D-10 chọn danh mục khi tải lên (Danh mục gợi ý tự áp dụng sau OCR / Do người dùng chọn, danh mục hệ thống "Chưa phân loại", documents.category_source); FR-04 OCR vùng ảnh nhúng trong trang PDF có lớp chữ; tab Gợi ý danh mục hiển thị danh mục đang áp dụng (sửa lỗi hiển thị "Đang dùng" lệch) | đặc tả v0.9 | xong (1) đặc tả v0.9 (#16); (2) OCR vùng ảnh (thử với PaddleOCR thật: đọc được chữ trong ảnh, đúng thứ tự đọc; dấu tiếng Việt vẫn sai như GUIDE mục 9); (3) danh mục tự động khi tải lên + tab Gợi ý danh mục thiết kế lại, migration 0109, script CSDL v0.9 (GUIDE mục 3) |
| **SDD v0.10** — dừng OCR (POST /api/jobs/{id}/cancel, nút Dừng có xác nhận), trang scan có khối chữ ký số vẫn OCR nội dung, model OCR chữ in mặc định bản mobile (văn bản scan 17 trang của nhóm: 1241 s → 67 s, nội dung tương đương; dấu tiếng Việt vẫn kém như GUIDE mục 9) | đặc tả v0.10 | cùng PR #17 |
| **Cải thiện OCR có dấu** (chữ in và viết tay còn sai dấu nhiều) | 2–3 ảnh mẫu kèm text đúng; biết là chữ in hay viết tay | chẩn đoán + 7 phương án + thứ tự làm: GUIDE mục 9 (ưu tiên VietOCR cho chữ in, DPI 300, lọc ký tự lạ) |
| **D-01** chốt giới hạn file/trang | đo trên máy triển khai | biến `MAX_UPLOAD_MB`, `MAX_PAGES` |
| Bắt buộc CI xanh trước khi merge | sửa ruleset (GUIDE 7.1) | 2 test chập chờn đã sửa (PR #4) nên có thể bật |
| Chép bản sao lưu ra ngoài máy | tùy nơi triển khai (ổ ngoài, cloud) | `BACKUP_DIR` (GUIDE 6.4) |
| CD (tự triển khai) | server | chưa làm |

## 5. Đã kiểm chứng khi chạy thật

- **Redis/Docker (06/10/2026):** Smart App Control đã tắt. Đã chuẩn bị chạy Redis + worker + beat trong Docker
  (`docker-start.cmd`, GUIDE mục 6) và gia cố cho Redis thật: tập session của user được gia hạn cùng session
  (trước đây khóa tài khoản có thể không thu hồi được session), bộ đếm rate limit INCR+EXPIRE NX nguyên tử,
  client Redis có timeout + API trả 503 khi mất Redis, visibility timeout broker ≥ 2×JOB_STALE_SECONDS,
  gửi job thử lại ngắn rồi báo QUEUE_UNAVAILABLE, worker `-P solo`, healthcheck/depends_on compose sửa lại,
  volume model OCR đúng quyền, `.dockerignore` gốc. CI: test backend trên Redis thật (`TEST_REDIS_URL`) và
  workflow `compose.yml` (build → up → E2E qua Nginx).
  **Đã chạy thật trên Docker Desktop 4.94 / WSL2 (06/10/2026):** build + up lần đầu thành công; smoke test, E2E
  9 passed/1 skipped qua Nginx; backend 102 passed trên Redis thật (`TEST_REDIS_URL`). Thử sự cố:

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
- **Lịch sử PR:** #1 sửa CI lần đầu · #2 hướng dẫn Git/CI · #3 đặc tả v0.6 + `notifications.message/link_url` ·
  #4 sao lưu/khôi phục (NFR-03) + sửa 2 test chập chờn · #5 thiết kế lại giao diện + icon · #6 nền tối, cập nhật tài liệu.
- **Test chập chờn (sửa ở PR #4):** `App.test.tsx` do sau đăng nhập có hai lần điều hướng chồng nhau làm trang đích
  mount 2 lần (lỗi app, test giờ đếm số lần mount); E2E `test_rollback_from_audit` do ba race trong test.
- **Sao lưu/khôi phục (16/10/2026):** thử thật trên project Docker tách biệt: sao lưu OK, phát hiện thiếu file (WARN),
  từ chối khi thiếu `--yes`/còn kết nối, khôi phục sau sự cố từ bản cũ nhất, lịch hằng ngày đúng giờ. Lần thử đầu bắt
  được 2 lỗi của script (biến hàm sh toàn cục làm khôi phục nhầm bản; dọn bản cũ xóa mất bản đang cần) — đã sửa.
- **Giao diện (16–17/10/2026):** sửa kèm nút menu mobile hiện trên desktop và cột thao tác lệch hàng bảng. Nền tối:
  màu biểu đồ kiểm tra bằng validator trên đúng màu nền thẻ của app (sáng `#ffffff`, tối `#111827`); trang scan giữ nền
  trắng ở cả hai chế độ (là nội dung); script đặt giao diện là file tĩnh `theme-init.js` vì CSP của Nginx chặn script inline.
