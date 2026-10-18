import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { mockFetch, renderWithProviders, SESSION } from "@/test/utils";

import { BackToList } from "./BackToList";
import { DocumentsListPage } from "./DocumentsListPage";

const DOC = {
  id: "d1",
  title: "Hợp đồng 01",
  file_type: "PDF",
  file_name: "a.pdf",
  category: { id: 1, name: "Hợp đồng" },
  owner: { id: "u1", full_name: "Officer" },
  total_pages: 1,
  needs_review_pages: 0,
  job_status: "completed",
  approval_status: "pending_review",
  share_mode: "internal",
  created_at: "2026-10-18T00:00:00Z",
};
const page = { items: [DOC], total: 1, page: 1, page_size: 20 };

describe("Danh sách tài liệu (FR-07 v0.7)", () => {
  it("có cột và bộ lọc trạng thái duyệt khi workflow bật, gửi approval_status lên server", async () => {
    const calls = mockFetch({
      "GET /api/auth/me": { body: { ...SESSION, features: ["workflow"] } },
      "GET /api/categories": { body: [] },
      "GET /api/documents": { body: page },
    });
    renderWithProviders(<DocumentsListPage />, { route: "/documents?approval_status=pending_review" });
    expect(await screen.findByText("Chờ duyệt", { selector: "span" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Duyệt" })).toBeInTheDocument();
    expect(screen.getByLabelText("Trạng thái duyệt")).toHaveValue("pending_review");
    expect(calls.some((c) => c.url.includes("approval_status=pending_review"))).toBe(true);
  });

  it("workflow tắt: không có cột/bộ lọc duyệt, bỏ qua approval_status còn trên URL", async () => {
    const calls = mockFetch({
      "GET /api/auth/me": { body: SESSION },
      "GET /api/categories": { body: [] },
      "GET /api/documents": { body: page },
    });
    renderWithProviders(<DocumentsListPage />, { route: "/documents?approval_status=published" });
    await screen.findByText("Hợp đồng 01");
    expect(screen.queryByRole("columnheader", { name: "Duyệt" })).toBeNull();
    expect(screen.queryByLabelText("Trạng thái duyệt")).toBeNull();
    expect(calls.some((c) => c.url.includes("approval_status"))).toBe(false);
  });

  it("nút quay lại trên trang chi tiết giữ bộ lọc của danh sách", async () => {
    const calls = mockFetch({
      "GET /api/auth/me": { body: SESSION },
      "GET /api/categories": { body: [] },
      "GET /api/documents": { body: page },
    });
    const list = renderWithProviders(<DocumentsListPage />, { route: "/documents?status=failed" });
    await screen.findByText("Hợp đồng 01");
    await userEvent.setup().type(screen.getByLabelText("Tìm theo tên"), "hop"); // từ khóa lên URL sau debounce
    await waitFor(() => expect(calls.some((c) => c.url.includes("q=hop"))).toBe(true));
    list.unmount();

    renderWithProviders(<BackToList />, { route: "/documents/d1" });
    // trong app, RequireAuth chỉ render trang khi phiên đã tải (bộ lọc lưu theo người dùng)
    await waitFor(() =>
      expect(screen.getByRole("link", { name: /Quay lại danh sách tài liệu/ })).toHaveAttribute(
        "href",
        "/documents?status=failed&q=hop",
      ),
    );
  });

  it("mở từ trang khác thì quay lại trang đó; bỏ qua đường dẫn ngoài", async () => {
    mockFetch({ "GET /api/auth/me": { body: SESSION } });
    const a = renderWithProviders(<BackToList />, {
      route: { pathname: "/documents/d1", state: { from: "/jobs?status=failed", fromLabel: "hàng đợi xử lý" } },
    });
    expect(await screen.findByRole("link", { name: /Quay lại hàng đợi xử lý/ })).toHaveAttribute(
      "href",
      "/jobs?status=failed",
    );
    a.unmount();
    renderWithProviders(<BackToList />, {
      route: { pathname: "/documents/d1", state: { from: "//evil.example", fromLabel: "x" } },
    });
    expect(await screen.findByRole("link", { name: /Quay lại danh sách tài liệu/ })).toHaveAttribute(
      "href",
      expect.stringMatching(/^\/documents/),
    );
  });

  it('nút "Được chia sẻ với tôi" lọc qua server và đổi thông báo khi rỗng (FR-13)', async () => {
    const calls = mockFetch({
      "GET /api/auth/me": { body: { ...SESSION, features: ["workflow"] } },
      "GET /api/categories": { body: [] },
      "GET /api/documents": ({ url }) => ({
        body: url.includes("shared=with_me")
          ? { items: [], total: 0, page: 1, page_size: 20 }
          : { ...page, items: [{ ...DOC, approval_status: "published" }] }, // chỉ tài liệu đã xuất bản có biểu tượng
      }),
    });
    renderWithProviders(<DocumentsListPage />, { route: "/documents" });
    expect(await screen.findByRole("img", { name: "Chia sẻ: Nội bộ" })).toBeInTheDocument(); // biểu tượng chế độ
    const toggle = screen.getByRole("button", { name: "Được chia sẻ với tôi" });
    expect(toggle).toHaveAttribute("aria-pressed", "false");
    await userEvent.setup().click(toggle);
    expect(await screen.findByText("Chưa có tài liệu nào được người khác chia sẻ với bạn.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Được chia sẻ với tôi" })).toHaveAttribute("aria-pressed", "true");
    expect(calls.some((c) => c.url.includes("shared=with_me"))).toBe(true);
  });
});
