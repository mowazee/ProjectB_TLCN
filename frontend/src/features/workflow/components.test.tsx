import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { DocumentOut } from "@/shared/api/types";
import { mockFetch, renderWithProviders, SESSION } from "@/test/utils";

import { ApprovalActions } from "./components";

const DOC = { id: "d1", title: "Quyết định 1" } as DocumentOut;

function render(actions: string[], status: string) {
  const calls = mockFetch({
    "GET /api/auth/me": { body: { ...SESSION, features: ["workflow"] } },
    "GET /api/documents/d1/approval": { body: { approval_status: status, allowed_actions: actions } },
    "POST /api/documents/d1/approval/return": { body: { approval_status: "draft", allowed_actions: [] } },
    "POST /api/documents/d1/approval/withdraw": { body: { approval_status: "draft", allowed_actions: ["submit"] } },
  });
  renderWithProviders(<ApprovalActions document={DOC} />);
  return calls;
}

describe("ApprovalActions - Rút lại, Trả lại (D-11)", () => {
  it("Trả lại cho người tải lên bắt buộc ghi chú", async () => {
    const user = userEvent.setup();
    const calls = render(["publish", "return"], "unpublished");
    await user.click(await screen.findByRole("button", { name: "Trả lại cho người tải lên" }));
    const confirm = screen.getByRole("button", { name: "Xác nhận" });
    expect(confirm).toBeDisabled();
    expect(screen.getByText(/người tải lên nhận thông báo kèm ghi chú/)).toBeInTheDocument();
    await user.type(screen.getByLabelText("Ghi chú cho người tải lên (bắt buộc)"), "Bổ sung số hiệu");
    await user.click(confirm);
    const post = calls.find((c) => c.method === "POST");
    expect(post?.url).toContain("/approval/return");
    expect(post?.body).toEqual({ comments: "Bổ sung số hiệu" });
  });

  it("chủ sở hữu Rút lại không cần ghi chú", async () => {
    const user = userEvent.setup();
    const calls = render(["withdraw"], "pending_review");
    await user.click(await screen.findByRole("button", { name: "Rút lại" }));
    expect(screen.getByText(/Tài liệu về Nháp để bạn chỉnh sửa/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Xác nhận" }));
    expect(calls.some((c) => c.method === "POST" && c.url.includes("/approval/withdraw"))).toBe(true);
  });
});

describe("Gửi duyệt khai báo bản cứng (D-12)", () => {
  function renderSubmit() {
    const calls = mockFetch({
      "GET /api/auth/me": { body: { ...SESSION, features: ["workflow", "borrowing"] } },
      "GET /api/documents/d1/approval": { body: { approval_status: "draft", allowed_actions: ["submit"] } },
      "GET /api/storage-locations": {
        body: [
          { id: 1, code: "KHO-A1", name: "Kho A", is_virtual: false },
          { id: 9, code: "KHO-CHUNG", name: "Kho chung (không có bản cứng)", is_virtual: true },
        ],
      },
      "GET /api/documents/d1/storage-location": { body: { storage_location: null, has_physical_copy: null } },
      "POST /api/documents/d1/approval/submit": { body: { approval_status: "pending_review", allowed_actions: [] } },
    });
    renderWithProviders(<ApprovalActions document={DOC} />);
    return calls;
  }

  it("bắt buộc chọn có/không; Có thì phải chọn kho/kệ thật", async () => {
    const user = userEvent.setup();
    const calls = renderSubmit();
    await user.click(await screen.findByRole("button", { name: "Gửi duyệt" }));
    const confirm = screen.getByRole("button", { name: "Xác nhận" });
    expect(confirm).toBeDisabled();
    await user.click(screen.getByLabelText(/Có — chọn kho\/kệ/));
    expect(confirm).toBeDisabled();
    const select = await screen.findByLabelText("Kho/kệ lưu trữ");
    expect(screen.queryByRole("option", { name: /Kho chung/ })).toBeNull();
    await user.selectOptions(select, "1");
    await user.click(confirm);
    const post = calls.find((c) => c.method === "POST");
    expect(post?.body).toEqual({ has_physical_copy: true, storage_location_id: 1 });
  });

  it("Không có bản cứng gửi has_physical_copy=false", async () => {
    const user = userEvent.setup();
    const calls = renderSubmit();
    await user.click(await screen.findByRole("button", { name: "Gửi duyệt" }));
    await user.click(screen.getByLabelText(/Không — đưa vào Kho chung/));
    await user.click(screen.getByRole("button", { name: "Xác nhận" }));
    expect(calls.find((c) => c.method === "POST")?.body).toEqual({ has_physical_copy: false });
  });
});
