import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { describe, expect, it } from "vitest";

import { mockFetch, renderWithProviders, SESSION } from "@/test/utils";

import { DocumentDetailPage } from "./DocumentDetailPage";

const WF_SESSION = { ...SESSION, features: ["workflow"] };
const doc = (over: Record<string, unknown>) => ({
  id: "d1",
  title: "Hợp đồng 01",
  document_code: null,
  file_name: "a.pdf",
  file_type: "PDF",
  mime_type: "application/pdf",
  bytes: 1000,
  lifecycle_status: "active",
  approval_status: "published",
  is_handwritten: false,
  category: { id: 1, name: "Hợp đồng" },
  owner: { id: SESSION.user.id, full_name: "Officer" },
  department_id: 1,
  created_at: "2026-10-18T00:00:00Z",
  updated_at: "2026-10-18T00:00:00Z",
  deleted_at: null,
  restore_deadline: null,
  total_pages: 0,
  needs_review_pages: 0,
  job_status: null,
  job_id: null,
  can_edit: true,
  share_mode: "internal",
  can_share: true,
  ...over,
});

function render(body: object) {
  mockFetch({
    "GET /api/auth/me": { body: WF_SESSION },
    "GET /api/documents/d1/pages": { body: [] },
    "GET /api/documents/d1/sharing": {
      body: {
        document_id: "d1",
        share_mode: "internal",
        is_published: true,
        owner_department: { id: 1, name: "Phòng A" },
        departments: [],
        users: [],
      },
    },
    "GET /api/departments": { body: [] },
    "GET /api/documents/d1": { body },
  });
  renderWithProviders(
    <Routes>
      <Route path="/documents/:id" element={<DocumentDetailPage />} />
    </Routes>,
    { route: "/documents/d1" },
  );
}

describe("Chi tiết tài liệu - chia sẻ (FR-13)", () => {
  it("chủ sở hữu tài liệu đã xuất bản: nhãn chế độ và nút Chia sẻ mở hộp thoại", async () => {
    render(doc({}));
    const btn = await screen.findByRole("button", { name: "Chia sẻ" });
    expect(btn).toBeEnabled();
    expect(screen.getByText("Nội bộ")).toBeInTheDocument();
    await userEvent.setup().click(btn);
    expect(await screen.findByRole("dialog", { name: 'Chia sẻ "Hợp đồng 01"' })).toBeInTheDocument();
  });

  it("chưa xuất bản: chủ sở hữu thấy nút mờ kèm lý do, chưa có nhãn chế độ", async () => {
    render(doc({ approval_status: "draft", can_share: false }));
    const btn = await screen.findByRole("button", { name: "Chia sẻ" });
    expect(btn).toBeDisabled();
    expect(btn).toHaveAccessibleDescription("Chỉ chia sẻ được tài liệu đã xuất bản");
    expect(screen.getByText("Áp dụng khi xuất bản")).toBeInTheDocument();
  });

  it("người được chia sẻ: không có nút Chia sẻ, Sửa, Xóa", async () => {
    render(doc({ owner: { id: "khac", full_name: "Người khác" }, can_share: false, can_edit: false }));
    await screen.findByText("Nội bộ");
    expect(screen.queryByRole("button", { name: "Chia sẻ" })).toBeNull();
    expect(screen.queryByRole("button", { name: /Sửa thông tin/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /Xóa/ })).toBeNull();
  });
});
