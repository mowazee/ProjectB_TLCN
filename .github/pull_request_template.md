## Tóm tắt
<!-- Thay đổi gì, vì sao. Ghi mã yêu cầu (FR-xx, P2-xx, NFR-xx, D-xx) và phiên bản SDD liên quan. -->

## Kiểm thử
<!-- Lệnh đã chạy và kết quả: pytest, npm test, e2e... Ảnh chụp nếu đổi giao diện. -->

## Checklist người tạo PR
- [ ] Đặc tả (SDD) đã cập nhật trước nếu đổi yêu cầu/phạm vi
- [ ] Có test cho hành vi mới, gồm ca lỗi/ca biên
- [ ] Đổi model có migration; đổi router đã sinh lại `docs/openapi.json` và `schema.d.ts`
- [ ] Không commit secret, `.env`, dữ liệu thật

## Kiểm soát đầu ra AI (CONTRIBUTING.md mục 5)
- [ ] Phần do AI sinh đã được đọc hiểu, giải thích được và đối chiếu tài liệu chính thức
- [ ] Lỗi của AI phát hiện trong PR (nếu có) đã ghi vào AI Usage Log

## Người review
- [ ] Đã đọc toàn bộ thay đổi, CI xanh, đồng ý merge
