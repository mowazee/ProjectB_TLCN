import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { mockFetch, renderWithProviders, SESSION } from "@/test/utils";

import { ReviewsPage } from "./ReviewsPage";

const ITEMS = [
  {
    document_id: "a",
    title: "Hồ sơ A",
    category_id: 1,
    submitted_by: "NV",
    submitted_at: null,
    validity_status: "effective",
    valid_until: null,
  },
  {
    document_id: "b",
    title: "Hồ sơ B",
    category_id: 1,
    submitted_by: "NV",
    submitted_at: null,
    validity_status: "unspecified",
    valid_until: null,
  },
];

function render() {
  const calls = mockFetch({
    "GET /api/auth/me": { body: { ...SESSION, features: ["workflow"] } },
    "GET /api/reviews": { body: { items: ITEMS, total: 2, page: 1, page_size: 20 } },
    "POST /api/reviews/bulk": {
      body: {
        batch_id: "x",
        succeeded: 1,
        failed: 1,
        results: [
          { document_id: "a", ok: true, approval_status: "published", error_code: null, error_message: null },
          {
            document_id: "b",
            ok: false,
            approval_status: null,
            error_code: "INVALID_TRANSITION",
            error_message: "Sai trạng thái",
          },
        ],
      },
    },
  });
  renderWithProviders(<ReviewsPage />);
  return calls;
}

describe("ReviewsPage - duyệt hàng loạt (FR-20)", () => {
  it("phải tích đủ checklist mới xác nhận; hiện kết quả từng tài liệu", async () => {
    const user = userEvent.setup();
    const calls = render();
    await user.click(await screen.findByLabelText("Chọn tất cả trên trang"));
    await user.click(screen.getByRole("button", { name: "Duyệt và xuất bản (2)" }));
    const confirm = screen.getByRole("button", { name: "Xác nhận" });
    expect(confirm).toBeDisabled();
    for (const label of [/Hiệu lực của tài liệu/, /Vị trí bản cứng/, /Kết quả OCR/, /Danh mục, tiêu đề/]) {
      await user.click(screen.getByLabelText(label));
    }
    await user.click(confirm);
    expect(calls.find((c) => c.method === "POST")?.body).toEqual({
      action: "approve_publish",
      document_ids: ["a", "b"],
      confirmed_checks: ["validity", "physical_copy", "extraction", "metadata"],
    });
    expect(await screen.findByText("1 thành công")).toBeInTheDocument();
    expect(screen.getByText(/Hồ sơ B: Sai trạng thái/)).toBeInTheDocument();
  });

  it("từ chối cần lý do chung; Kiểm tra lại đóng hộp thoại và giữ lựa chọn", async () => {
    const user = userEvent.setup();
    const calls = render();
    await user.click(await screen.findByLabelText("Chọn Hồ sơ A"));
    await user.click(screen.getByRole("button", { name: "Từ chối (1)" }));
    await user.click(screen.getByRole("button", { name: "Kiểm tra lại" }));
    expect(screen.getByLabelText("Chọn Hồ sơ A")).toBeChecked();
    await user.click(screen.getByRole("button", { name: "Từ chối (1)" }));
    expect(screen.getByRole("button", { name: "Xác nhận" })).toBeDisabled();
    await user.type(screen.getByLabelText("Lý do từ chối chung (bắt buộc)"), "Thiếu chữ ký");
    await user.click(screen.getByRole("button", { name: "Xác nhận" }));
    expect(calls.find((c) => c.method === "POST")?.body).toEqual({
      action: "reject",
      document_ids: ["a"],
      comments: "Thiếu chữ ký",
      confirmed_checks: [],
    });
  });
});
