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
