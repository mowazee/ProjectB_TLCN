import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { mockFetch, renderWithProviders, SESSION } from "@/test/utils";

import { RolesPage } from "./RolesPage";

const ADMIN = { ...SESSION, roles: ["ADMIN"] };
const ROLES = [
  {
    id: 1,
    name: "ADMIN",
    description: "Quản trị viên hệ thống",
    summary: "Toàn quyền",
    permissions: ["Quản lý người dùng"],
    member_count: 1,
  },
  {
    id: 4,
    name: "VIEWER",
    description: "Người dùng thông thường",
    summary: "Chỉ xem",
    permissions: ["Xem tài liệu đã xuất bản", "Tải file gốc"],
    member_count: 2,
  },
];
const user = (id: string, username: string, roles: string[]) => ({
  id,
  username,
  email: `${username}@x.vn`,
  full_name: username.toUpperCase(),
  phone: null,
  is_active: true,
  department_id: null,
  roles,
  last_login_at: null,
  created_at: "2026-10-18T00:00:00Z",
});

describe("Trang Nhóm quyền (FR-12)", () => {
  it("hiển thị vai trò, ma trận quyền; chỉ cho gỡ người còn vai trò khác", async () => {
    const calls = mockFetch({
      "GET /api/auth/me": { body: ADMIN },
      "GET /api/roles": { body: ROLES },
      "GET /api/departments": { body: [] },
      "GET /api/users": ({ url }) => ({
        body: {
          items: url.includes("role=VIEWER")
            ? [user("u1", "chiem", ["VIEWER"]), user("u2", "hai", ["VIEWER", "OFFICER"])]
            : [user(SESSION.user.id, "admin", ["ADMIN"])],
          total: url.includes("role=VIEWER") ? 2 : 1,
          page: 1,
          page_size: 100,
        },
      }),
      "PATCH /api/users/u2": { body: user("u2", "hai", ["OFFICER"]) },
    });
    const u = userEvent.setup();
    renderWithProviders(<RolesPage />);

    // Admin đang đăng nhập: không tự gỡ vai trò Quản trị viên của chính mình
    const adminRow = (await screen.findByText("@admin")).closest("tr")!;
    expect(within(adminRow).getByRole("button", { name: /Gỡ/ })).toBeDisabled();

    await u.click(screen.getByRole("tab", { name: /Người dùng thông thường/ }));
    expect(await screen.findByText("Tải file gốc")).toBeInTheDocument(); // ma trận quyền chỉ đọc
    expect(screen.getByText("2 thành viên")).toBeInTheDocument();
    const only = (await screen.findByText("@chiem")).closest("tr")!;
    expect(within(only).getByRole("button", { name: /Gỡ/ })).toBeDisabled(); // còn mỗi một vai trò
    const multi = screen.getByText("@hai").closest("tr")!;
    await u.click(within(multi).getByRole("button", { name: /Gỡ/ }));
    await waitFor(() => expect(calls.some((c) => c.method === "PATCH")).toBe(true));
    expect(calls.find((c) => c.method === "PATCH")?.body).toEqual({ roles: ["OFFICER"] });
  });
});
