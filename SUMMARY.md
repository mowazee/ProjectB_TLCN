# Tóm tắt trạng thái ProjectB (baseline SDD v0.6) — cập nhật 16/10/2026

## 1. Đã hoàn thành

| Hạng mục | Nội dung | Bằng chứng |
|---|---|---|
| Backend MVP | 9 module lõi (auth, users, categories, documents, jobs, ocr, search, dashboard, audit), 4 lớp mỗi module | 50+ test API/unit |
| Backend P2 | P2-01…P2-09 (10 module/file bổ sung), cờ `FEATURES_ENABLED`, router tắt → 404 | test_p2_*.py |
| Điểm mở rộng | ModuleSpec + registry, job kind registry (`jobs.run`), event sau commit, port OcrEngine/Storage/Notifier, API truy vấn công khai, UI registry + slot | import-linter 5 contract KEPT; ESLint chặn import sai ranh giới |
| CSDL | Alembic `0001_core` + `0101…0106` (mỗi module P2 một revision); trigger audit append-only (cho phép ON DELETE SET NULL); CHECK `kind` mở rộng ở 0105; `notifications.message/link_url` ở 0106 | `alembic check` sạch trên SQLite và PostgreSQL; upgrade/downgrade/upgrade |
| Frontend | React 19 + TS + Vite 8, React Router 7, TanStack Query 5, CSS Modules, Chart.js; 15 feature (6 lõi + 9 P2, lazy); types sinh từ OpenAPI | 17 test Vitest; tsc/eslint/prettier sạch |
| Hạ tầng | Nginx (SPA + /api), Dockerfile backend/frontend, compose (profile hw, rag), compose.dev, Makefile, CI 3 workflow (ma trận cờ P2) | — |
| Đánh giá | `backend/eval/`: CER/WER/độ chính xác ký tự, hiệu chỉnh ngưỡng, precision/recall trích xuất, top-1 phân loại | chạy thử với PaddleOCR thật trên dữ liệu tổng hợp |
| Demo | `demo-start.cmd` / `demo-stop.cmd` (PostgreSQL riêng `.demo\`, worker, beat, API, React :8080) | đã chạy end-to-end với PaddleOCR thật |

### Kết quả kiểm thử (05/10/2026)

| Bộ | Kết quả |
|---|---|
| Backend pytest (SQLite), cờ tắt / mọi cờ bật | 105 passed / 105 passed (16/10, sau migration 0106) |
| Backend pytest trên Redis thật (Docker), cờ tắt / mọi cờ bật | 104 passed / 104 passed |
| Bản Docker Compose (Redis + worker + beat + Nginx): E2E | 9 passed, 1 skipped |
| Backend pytest trên PostgreSQL 18, cờ tắt / mọi cờ bật | 90/90 passed cả hai (trước khi thêm 3 test eval) |
| Frontend Vitest | 17 passed |
| E2E Playwright trên demo thật, mọi cờ bật | 9 passed, 1 skipped (test dành cho cờ tắt) |
| E2E chế độ chỉ MVP (`-Mvp`) | 6 passed, 4 skipped (các test P2 tự bỏ qua khi cờ tắt) |
| ruff, ruff format, mypy, lint-imports, ESLint, tsc, Prettier | sạch |

## 2. Truy vết yêu cầu → hiện thực → test

| Mã | Backend | Frontend | Test chính |
|---|---|---|---|
| FR-01 | auth, users | features/auth, admin/UsersPage | test_auth.py (401/403/429, CSRF, Origin, khóa user thu hồi session) |
| FR-02 | categories | admin/CategoriesPage | test_admin.py (ngừng dùng không chọn được, tài liệu cũ vẫn hiển thị) |
| FR-03 | documents/upload, file_inspector | documents/UploadPage | test_documents.py (415, 413, lỗi storage không tạo job) |
| FR-04 | jobs/runner, ocr/run_ocr, beat requeue | jobs/JobStatus (poll 2s) | test_ocr_jobs.py (retry không trùng, needs_review, engine lỗi, job treo) |
| FR-05 | ocr/editor | ocr/EditorPage (409 giữ draft) | test_editor_search.py; EditorForm.test.tsx; e2e 409 |
| FR-06 | search (FTS PostgreSQL / substring SQLite, không dấu) | search/SearchPage | test_editor_search.py; e2e |
| FR-07 | documents/manage, purge (beat) | documents/TrashPage | test_documents.py (410 quá hạn, purge giữ audit, bỏ qua job đang chạy) |
| FR-08 | dashboard, audit | dashboard (Chart.js), admin/AuditPage | test_editor_search.py, test_admin.py |
| P2-01 | workflow | workflow (nút, lịch sử, /reviews) | test_p2_workflow.py; e2e |
| P2-02 | search/highlight_module | highlight (pageOverlays) | test_p2_versions_highlight.py; HighlightOverlay.test.tsx; e2e |
| P2-03 | ocr/handwriting_module (queue ocr_hw) | handwriting (uploadFields, reprocess) | test_p2_handwriting.py |
| P2-04 | extraction (job EXTRACT, UNIQUE) | extraction (tab) | test_p2_extraction_classification.py |
| P2-05 | classification (job CLASSIFY, scikit-learn TF-IDF + Logistic Regression) | classification (tab) | test_p2_extraction_classification.py |
| P2-06 | ocr/versions_module (difflib) | versions (editorTools) | test_p2_versions_highlight.py; e2e |
| P2-07 | borrowing + notifications (beat nhắc quá hạn) | borrowing, notifications (chuông) | test_p2_borrowing.py, test_p2_workflow.py |
| P2-08 | imports (job BULK_IMPORT, ZIP an toàn) | imports | test_p2_imports.py; e2e |
| P2-09 | rollback | rollback (auditRowActions) | test_p2_rollback.py; e2e |
| NFR-09 | registry + cờ | registry.ts | toàn bộ test chạy lại với `TEST_FEATURES=all`; test_p2_flags.py; registry.test.ts |

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

## 4. Việc còn lại / rủi ro

- **NFR-08 chưa có số liệu chính thức:** cần tập test thật (scan rõ, scan khó, chữ viết tay ≥ 30 trang mỗi loại) → chạy `eval/ocr_eval.py`.
  Thử trên dữ liệu tổng hợp: scan rõ ~91%, scan khó ~90% (chỉ để kiểm tra quy trình). PaddleOCR `vi` hay mất dấu (WER cao).
- **P2-03 chưa kiểm chứng mục tiêu > 70%:** baseline là PaddleOCR; adapter VietOCR đã viết nhưng chưa cài/thử (cần mẫu chữ viết tay thật).
- **Precision/recall P2-04 và top-1 P2-05** cần tập mẫu có nhãn (`eval/extraction_eval.py`, `eval/classification_eval.py`).
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
- **CI** đã viết nhưng chưa chạy trên GitHub (thư mục chưa là git repo).
- Chưa có kế hoạch sao lưu/khôi phục tự động (NFR-03) — GUIDE mục 6 mới mô tả thủ công.
