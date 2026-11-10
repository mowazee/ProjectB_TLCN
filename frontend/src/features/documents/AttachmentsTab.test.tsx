import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { DocumentOut } from "@/shared/api/types";
import { mockFetch, renderWithProviders, SESSION } from "@/test/utils";

import { AttachmentsTab } from "./AttachmentsTab";

const ITEM = {
  id: "a1",
  file_name: "phu-luc.docx",
  mime_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  bytes: 2048,
  uploaded_by: null,
  created_at: "2026-11-10T03:00:00Z",
};

function render(canEdit: boolean) {
  const calls = mockFetch({
    "GET /api/auth/me": { body: SESSION },
    "GET /api/documents/d1/attachments": { body: [ITEM] },
    "POST /api/documents/d1/attachments": { status: 201, body: [ITEM] },
    "DELETE /api/documents/d1/attachments/a1": { status: 204, body: null },
  });
  const doc = { id: "d1", title: "Hồ sơ", can_edit: canEdit, edit_lock_reason: canEdit ? null : "Đã xuất bản" };
  renderWithProviders(<AttachmentsTab document={doc as DocumentOut} />);
  return calls;
}

describe("AttachmentsTab (FR-15)", () => {
  it("người có quyền sửa thêm và xóa; luôn có link tải từng file và tải cả bộ", async () => {
    const user = userEvent.setup();
    const calls = render(true);
    const link = await screen.findByRole("link", { name: "phu-luc.docx" });
    expect(link.getAttribute("href")).toBe("/api/documents/d1/attachments/a1/file");
    expect(screen.getByRole("link", { name: /Tải cả bộ/ }).getAttribute("href")).toBe("/api/documents/d1/bundle");
    await user.upload(screen.getByLabelText("Chọn tài liệu đi kèm"), new File(["x"], "b.txt", { type: "text/plain" }));
    const post = calls.find((c) => c.method === "POST");
    expect((post?.body as FormData).getAll("files")).toHaveLength(1);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    await user.click(screen.getByRole("button", { name: "Xóa phu-luc.docx" }));
    expect(calls.some((c) => c.method === "DELETE")).toBe(true);
  });

  it("không có quyền sửa: chỉ xem và tải, hiện lý do", async () => {
    render(false);
    expect(await screen.findByRole("link", { name: "phu-luc.docx" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Thêm tài liệu đi kèm/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /Xóa/ })).toBeNull();
    expect(screen.getByText("Đã xuất bản")).toBeInTheDocument();
  });
});
