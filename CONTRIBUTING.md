# Quy ước đóng góp mã nguồn (coding convention)

Áp dụng cho mọi thay đổi trong repo. Chi tiết kiến trúc ở "Đặc tả đề tài" (file 2) mục 4; quy trình Git ở GUIDE mục 7.

## 1. Quy trình

1. Mọi thay đổi đi qua **nhánh + Pull Request**, không push thẳng `main`. Tên nhánh: `feat/…`, `fix/…`, `docs/…`, `ci/…`, `test/…`.
2. Thay đổi yêu cầu/phạm vi: **cập nhật đặc tả (SDD) trước**, PR hiện thực sau (SDD mục 1).
3. Mỗi PR có **ít nhất 1 thành viên khác review và approve** trước khi squash merge; CI phải xanh.
4. Commit message: `loại(phạm vi): mô tả ngắn` — loại ∈ `feat`, `fix`, `docs`, `test`, `ci`, `refactor`, `chore`;
   phạm vi là mã yêu cầu khi có (vd. `feat(FR-19): …`). Viết tiếng Việt, mô tả "vì sao" trong thân commit/PR.
5. PR điền đủ mẫu (`.github/pull_request_template.md`): mã yêu cầu, bằng chứng kiểm thử, checklist review và kiểm soát
   đầu ra AI.

## 2. Backend (Python 3.12, FastAPI)

| Quy ước | Công cụ kiểm tra (CI chặn) |
|---|---|
| Mỗi module 4 lớp `presentation → application → domain`, `infrastructure`; domain là Python thuần | import-linter 5 contract (`lint-imports`) |
| Module P2 không bị module lõi import; module chỉ gọi nhau qua `application` | import-linter |
| Định dạng, sắp xếp import, dòng ≤ 120 ký tự | `ruff format`, `ruff check` |
| Có type hint đầy đủ | `mypy` |
| Không dùng hàm nguy hiểm, không hardcode secret | `bandit`, gitleaks |
| Tên: file/hàm `snake_case`, lớp `PascalCase`, hằng `UPPER_CASE`; lỗi nghiệp vụ dùng `AppError` có `code` ổn định | review |
| Đổi model → kèm migration Alembic (một revision/module); đổi router → sinh lại `docs/openapi.json` + `schema.d.ts` | `alembic check`, openapi-drift |
| Cấu hình chỉ qua biến môi trường (`app/shared/config.py`, `.env`); không commit `.env` | gitleaks, review |

## 3. Frontend (React 19 + TypeScript)

| Quy ước | Công cụ kiểm tra (CI chặn) |
|---|---|
| Mỗi tính năng một thư mục `src/features/<feature>` khai báo `manifest.tsx`; dùng chung qua `src/shared` | ESLint (ranh giới import) |
| Component `PascalCase.tsx`, hook `useXxx`, test đặt cạnh file `*.test.tsx` | ESLint, review |
| Kiểu dữ liệu API lấy từ `shared/api/types.ts` (sinh từ OpenAPI), không tự khai báo lại | `tsc`, openapi-drift |
| Màu dùng biến CSS (sáng/tối), icon `lucide-react` (GUIDE 4.2) | review |
| Định dạng | Prettier (`npm run format:check`) |

## 4. Chất lượng và bảo mật (CI)

| Kiểm tra | Workflow | Ngưỡng |
|---|---|---|
| Lint, kiểu, ranh giới module | backend.yml, frontend.yml | 0 lỗi |
| Test + độ phủ (artifact `backend-coverage`, `frontend-coverage`) | backend.yml, frontend.yml | 100% pass |
| Lỗ hổng thư viện | pip-audit, `npm audit --audit-level=high`, Trivy | 0 lỗ hổng đã biết / 0 HIGH-CRITICAL có bản sửa |
| Secret trong lịch sử Git | security.yml (gitleaks, cấu hình `.gitleaks.toml`) | 0 secret |
| Phân tích tĩnh, trùng lặp mã, Quality Gate | SonarCloud Automatic Analysis (check "SonarCloud Code Analysis" trên mỗi PR) | 0 Blocker/Critical, trùng lặp ≤ 3% |

**SonarCloud:** đã bật *Automatic Analysis* cho repo (organization `mowazee`): SonarCloud tự quét mỗi PR và nhánh
`main`, kết quả ở https://sonarcloud.io/project/overview?id=mowazee_ProjectB_TLCN. Phạm vi phân tích cấu hình trong
`.sonarcloud.properties`. Độ phủ test không đưa lên SonarCloud (Automatic Analysis không nhận báo cáo coverage) mà lấy từ
artifact `backend-coverage`, `frontend-coverage` của CI. Action bên thứ ba trong workflow mới được ghim bằng commit SHA.

## 5. Kiểm soát mã do AI hỗ trợ

Nhóm có dùng Claude Code để sinh mã và tài liệu (kê khai trong AI Usage Log). Trước khi approve một PR có phần do AI
sinh, người review kiểm tra:

- [ ] Đọc hiểu và giải thích được từng thay đổi (nội dung làm gì, vì sao cần, bỏ đi thì ảnh hưởng gì).
- [ ] Chạy test, lint tại máy; CI xanh; có test cho hành vi mới và ca biên/ca lỗi.
- [ ] Đối chiếu với đặc tả (SDD) và tài liệu chính thức của thư viện; không có API/tham số "bịa".
- [ ] Không có mã sao chép mà không rõ giấy phép; thư viện mới có giấy phép phù hợp.
- [ ] Prompt và mã không chứa dữ liệu nhạy cảm (mật khẩu, dữ liệu thật của người dùng).
- [ ] Lỗi/ảo giác của AI phát hiện được ghi vào AI Usage Log kèm commit sửa.
