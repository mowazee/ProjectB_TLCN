import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { Snippet } from "@/features/search";
import { mockFetch, renderWithProviders, SESSION } from "@/test/utils";

import { AppRoutes } from "./App";

describe("Router + session (SDD mục 13, 15)", () => {
  it("chưa đăng nhập: chuyển về /login; đăng nhập xong quay lại route dự định", async () => {
    let loggedIn = false;
    mockFetch({
      "GET /api/auth/me": () =>
        loggedIn ? { body: SESSION } : { status: 401, body: { error: { code: "UNAUTHENTICATED", message: "x" } } },
      "POST /api/auth/login": () => {
        loggedIn = true;
        return { body: SESSION };
      },
      "GET /api/search": { body: { items: [], total: 0, page: 1, page_size: 10 } },
      "GET /api/categories": { body: [] },
    });
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, { route: "/search" });
    await user.type(await screen.findByLabelText("Tên đăng nhập hoặc email"), "officer");
    await user.type(screen.getByLabelText("Mật khẩu"), "secret");
    await user.click(screen.getByRole("button", { name: "Đăng nhập" }));
    expect(await screen.findByRole("heading", { name: "Tìm kiếm nội dung" })).toBeInTheDocument();
  });

  it("đăng nhập sai: hiển thị lỗi từ envelope", async () => {
    mockFetch({
      "GET /api/auth/me": { status: 401, body: { error: { code: "UNAUTHENTICATED", message: "x" } } },
      "POST /api/auth/login": {
        status: 401,
        body: { error: { code: "INVALID_CREDENTIALS", message: "Sai tên đăng nhập hoặc mật khẩu" } },
      },
    });
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, { route: "/login" });
    await user.type(await screen.findByLabelText("Tên đăng nhập hoặc email"), "x");
    await user.type(screen.getByLabelText("Mật khẩu"), "y");
    await user.click(screen.getByRole("button", { name: "Đăng nhập" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Sai tên đăng nhập hoặc mật khẩu");
  });

  it("route P2 chỉ có khi cờ bật (tắt -> không tìm thấy trang)", async () => {
    mockFetch({ "GET /api/auth/me": { body: { ...SESSION, roles: ["APPROVER"] } } });
    renderWithProviders(<AppRoutes />, { route: "/reviews" });
    expect(await screen.findByText("Không tìm thấy trang")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Duyệt tài liệu" })).not.toBeInTheDocument();
  });

  it("route P2 hiển thị khi cờ bật", async () => {
    mockFetch({
      "GET /api/auth/me": { body: { ...SESSION, roles: ["APPROVER"], features: ["workflow"] } },
      "GET /api/reviews": { body: { items: [], total: 0, page: 1, page_size: 20 } },
    });
    renderWithProviders(<AppRoutes />, { route: "/reviews" });
    expect(await screen.findByRole("heading", { name: "Hàng chờ duyệt" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Duyệt tài liệu" })).toBeInTheDocument();
  });
});

describe("Snippet tìm kiếm", () => {
  it("đánh dấu đúng vùng khớp, hiển thị như text", () => {
    const { container } = renderWithProviders(
      <Snippet hit={{ page_number: 1, snippet: "Biên bản <b>nghiệm thu</b>", match_start: 12, match_end: 22 }} />,
    );
    expect(container.querySelector("mark")?.textContent).toBe("nghiệm thu");
    expect(container.querySelector("b")).toBeNull(); // không chèn HTML
  });
});
