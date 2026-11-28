import { fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { mockFetch, renderWithProviders, SESSION } from "@/test/utils";

import { GuidePage } from "./GuidePage";

const GUIDE = {
  id: "g1",
  title: "Hướng dẫn tải lên tài liệu",
  description: "Các bước tải lên và OCR",
  file_name: "huong-dan.pdf",
  mime_type: "application/pdf",
  bytes: 2048,
  inline: true,
  uploaded_by: "Quản trị viên",
  created_at: "2026-11-28T03:00:00Z",
  updated_at: "2026-11-28T03:00:00Z",
};
const LIST = { body: { items: [GUIDE], total: 1, page: 1, page_size: 20 } };

describe("GuidePage (FR-21, v0.16)", () => {
  it("người dùng thường: thấy danh sách, mở file, không có nút quản trị", async () => {
    mockFetch({ "GET /api/auth/me": { body: { ...SESSION, roles: ["OFFICER"] } }, "GET /api/guides": LIST });
    renderWithProviders(<GuidePage />);
    const link = await screen.findByRole("link", { name: "Hướng dẫn tải lên tài liệu" });
    expect(link.getAttribute("href")).toBe("/api/guides/g1/file");
    expect(screen.getByRole("columnheader", { name: "Người đăng" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Tải lên tài liệu/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /Xóa/ })).toBeNull();
  });

  it("Admin: tải lên tài liệu, tìm kiếm gửi tham số q, xóa có xác nhận", async () => {
    const user = userEvent.setup();
    const calls = mockFetch({
      "GET /api/auth/me": { body: { ...SESSION, roles: ["ADMIN"] } },
      "GET /api/guides": LIST,
      "POST /api/guides": { status: 201, body: GUIDE },
      "DELETE /api/guides/g1": { status: 204, body: null },
    });
    renderWithProviders(<GuidePage />);
    await user.click(await screen.findByRole("button", { name: /Tải lên tài liệu/ }));
    await user.upload(screen.getByLabelText(/^File/), new File(["%PDF-1.4"], "hd.pdf", { type: "application/pdf" }));
    await user.type(screen.getByLabelText(/Tiêu đề/), "Hướng dẫn mới");
    // jsdom không coi file do user.upload gán là "đã chọn" khi kiểm tra required: gửi form trực tiếp
    fireEvent.submit(document.getElementById("guide-upload") as HTMLFormElement);
    await vi.waitFor(() => expect(calls.some((c) => c.method === "POST")).toBe(true));

    await user.type(screen.getByLabelText("Tìm kiếm tài liệu hướng dẫn"), "tải lên");
    await vi.waitFor(() =>
      expect(calls.some((c) => new URL(c.url, "http://x").searchParams.get("q") === "tải lên")).toBe(true),
    );

    vi.spyOn(window, "confirm").mockReturnValue(true);
    await user.click(screen.getByRole("button", { name: "Xóa Hướng dẫn tải lên tài liệu" }));
    await vi.waitFor(() => expect(calls.some((c) => c.method === "DELETE")).toBe(true));
  });
});
