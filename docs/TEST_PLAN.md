# Kế hoạch kiểm thử

Phiên bản áp dụng: SDD v0.15. Mục tiêu: chứng minh mọi tiêu chí nghiệm thu (FR, P2, NFR) bằng kiểm thử tự động chạy lại
được, chặn hồi quy trước khi merge, và có số liệu cho các NFR định lượng.

## 1. Phạm vi

| Trong phạm vi | Ngoài phạm vi |
|---|---|
| MVP (FR-01…FR-21), P2-01…P2-09, NFR-01…NFR-09, quy tắc nghiệp vụ BR-01…BR-22 ([BUSINESS_RULES.md](BUSINESS_RULES.md)) | P3 (RAG), độ chính xác mô hình OCR/phân loại trên dữ liệu thật quy mô lớn (đo riêng bằng `backend/eval/`, NFR-08) |

## 2. Các tầng kiểm thử

| Tầng | Công cụ | Nội dung | Vị trí | Chạy ở |
|---|---|---|---|---|
| 1. Unit | pytest, Vitest | Domain thuần (state machine, policy quyền, hiệu lực, phân tích manifest, chuẩn hóa tìm kiếm), tiện ích React | `backend/tests/test_*domain*`, `frontend/src/**/*.test.ts` | CI mỗi PR |
| 2. Integration | pytest + PostgreSQL 18 + Redis thật | Repository, migration (`alembic upgrade/check/downgrade`), FTS, session store, job runner, beat task | `backend/tests/` (CI dùng `TEST_DATABASE_URL`, `TEST_REDIS_URL`) | CI mỗi PR, 6 tổ hợp cờ P2 |
| 3. API / hợp đồng | pytest + TestClient; openapi-drift | Mọi endpoint: quyền (401/403), dữ liệu sai (422), trạng thái sai (409), luồng nghiệp vụ; types React sinh từ OpenAPI | `backend/tests/test_*.py`; `frontend.yml` | CI mỗi PR |
| 4. Component UI | Vitest + Testing Library | Trang/hộp thoại: hiển thị theo quyền, form, bộ lọc, gọi API đúng tham số | `frontend/src/**/*.test.tsx` | CI mỗi PR |
| 5. E2E | Playwright (Python) | Luồng người dùng thật qua trình duyệt: tải lên → OCR → sửa (409) → tìm kiếm → duyệt → xuất bản → chia sẻ, nhập hàng loạt, rollback | `tests/e2e/` | CI 3 tổ hợp cờ; `compose.yml` qua Nginx |
| 6. Phi chức năng | `tests/load/load_test.py`; bandit, pip-audit, npm audit, Trivy, gitleaks; sao lưu/khôi phục | Hiệu năng NFR-04 (p95 ≤ 2 s), bảo mật NFR-02, tin cậy NFR-03 (Redis restart, kill worker, khôi phục từ bản sao lưu) | `tests/load/`, `security.yml`, `compose.yml` | Tải: chạy tay trên demo/staging; còn lại CI |

## 3. Môi trường

| Môi trường | Dùng cho |
|---|---|
| SQLite + bộ nhớ (máy dev) | Chạy nhanh toàn bộ test backend trước khi đẩy PR |
| GitHub Actions: PostgreSQL 18, Redis 8, Chromium | CI chính thức (kết quả để nghiệm thu) |
| Docker Compose (Nginx, API, worker, beat) | E2E giống production, sao lưu/khôi phục, kiểm thử tải |

## 4. Tiêu chí vào / ra

- **Vào (bắt đầu kiểm thử một PR):** đặc tả đã cập nhật; mã build được; lint, kiểu sạch ở máy dev.
- **Ra (được merge):** 100% test pass trên CI; không giảm độ phủ backend dưới 85%; 0 lỗ hổng HIGH/CRITICAL có bản sửa;
  0 secret; mọi lỗi Critical/Blocker đã đóng kèm test hồi quy.
- **Nghiệm thu (trước bảo vệ):** 100% test pass ở lần CI cuối; 0 defect Critical/Blocker mở; kiểm thử tải đạt NFR-04
  trên staging; thực nghiệm người dùng đạt KPI đã cam kết.

## 5. Số liệu hiện tại (28/11/2026)

| Chỉ số | Giá trị | Nguồn |
|---|---|---|
| Test backend | 509 passed, 1 skipped (mặc định và mọi cờ P2) | `pytest -q`; CI backend |
| Test frontend | 82 passed (25 file) | `npm test` |
| E2E | xanh trên 3 tổ hợp cờ (mvp, p2-dot-1, p2-tat-ca) | CI e2e |
| Độ phủ dòng lệnh backend | 93% | artifact `backend-coverage` |
| Độ phủ dòng lệnh frontend | 66,6% | artifact `frontend-coverage` |
| Tỉ lệ build xanh | ~96% (187/194 lượt chạy gần nhất) | lịch sử GitHub Actions |
| Kiểm thử tải NFR-04 | chưa đo trên staging | `tests/load/load_test.py` |

## 6. Truy vết test → tiêu chí nghiệm thu

- Bảng truy vết yêu cầu → module → bảng dữ liệu → **kiểm thử chính** cho từng FR/P2/NFR: SDD mục 9 và SUMMARY.md mục 2.
- Quy tắc nghiệp vụ → test: cột "Test" trong [BUSINESS_RULES.md](BUSINESS_RULES.md).
- File test ghi mã yêu cầu ở docstring đầu file (vd. `"""FR-19 (SDD v0.14, D-14): hiệu lực tài liệu."""`); ca âm (403/409/422)
  và ca biên (ngày hết hạn = hôm nay, giới hạn 20 tài liệu, manifest thiếu file…) nằm cùng file với ca thuận.

## 7. Quản lý lỗi (defect)

- Ghi lỗi bằng **GitHub Issues** theo mẫu `.github/ISSUE_TEMPLATE/bug_report.yml` (mức độ, bước tái hiện, kết quả
  mong đợi/thực tế, nguyên nhân và PR sửa khi đóng).
- Vòng đời: *Mở* → *Đang sửa* (PR liên kết `Fixes #n`) → *Đã sửa* (PR merge, có test hồi quy) → *Đóng*.
- Mỗi lỗi khi sửa **phải có test hồi quy** tái hiện lỗi trước khi sửa.

## 8. Chạy kiểm thử tải (NFR-04)

```powershell
# hệ thống đang chạy (demo hoặc Docker) và đã nạp dữ liệu demo
backend\.venv\Scripts\python.exe tests/load/load_test.py --base http://127.0.0.1:8080 --users 20 --duration 60 --json load-result.json
```

In p50/p95/p99 theo endpoint (danh sách, tìm kiếm, chi tiết, dashboard), số yêu cầu/giây, tỉ lệ lỗi; mã thoát 1 nếu p95
vượt 2 000 ms hoặc lỗi > 1%. Lưu `load-result.json` làm minh chứng.
