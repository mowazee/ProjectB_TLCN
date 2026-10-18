import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { mockFetch, renderWithProviders, SESSION } from "@/test/utils";

import { AccountPage } from "./AccountPage";

const ACCOUNT = {
  id: "u1",
  username: "officer",
  email: "officer@x.vn",
  full_name: "Nguyễn Văn A",
  phone: null,
  department_id: 1,
  department_name: "Phòng A",
  roles: ["OFFICER"],
  last_login_at: null,
  created_at: "2026-10-18T00:00:00Z",
};

describe("Trang Tài khoản của tôi (FR-09)", () => {
  it("đổi mật khẩu: kiểm nhập lại ở client, báo lỗi mật khẩu hiện tại sai từ server", async () => {
    const calls = mockFetch({
      "GET /api/auth/me": { body: SESSION },
      "GET /api/account": { body: ACCOUNT },
      "POST /api/account/password": {
        status: 400,
        body: { error: { code: "WRONG_PASSWORD", message: "Mật khẩu hiện tại không đúng" } },
      },
    });
    const u = userEvent.setup();
    renderWithProviders(<AccountPage />);

    expect(await screen.findByText("Phòng A")).toBeInTheDocument(); // vai trò/phòng ban chỉ hiển thị
    await u.type(screen.getByLabelText("Mật khẩu hiện tại"), "sai");
    await u.type(screen.getByLabelText("Mật khẩu mới"), "MatKhauMoi1");
    await u.type(screen.getByLabelText("Nhập lại mật khẩu mới"), "MatKhauKhac");
    expect(screen.getByText("Mật khẩu nhập lại không khớp")).toBeInTheDocument();
    const submit = screen.getByRole("button", { name: "Đổi mật khẩu" });
    expect(submit).toBeDisabled();

    await u.clear(screen.getByLabelText("Nhập lại mật khẩu mới"));
    await u.type(screen.getByLabelText("Nhập lại mật khẩu mới"), "MatKhauMoi1");
    await u.click(submit);
    expect(await screen.findByText("Mật khẩu hiện tại không đúng")).toBeInTheDocument();
    expect(calls.find((c) => c.url.endsWith("/api/account/password"))?.body).toEqual({
      current_password: "sai",
      new_password: "MatKhauMoi1",
    });
  });

  it("đổi mật khẩu thành công thì lấy lại phiên (csrf_token mới)", async () => {
    const calls = mockFetch({
      "GET /api/auth/me": { body: SESSION },
      "GET /api/account": { body: ACCOUNT },
      "POST /api/account/password": { status: 204 },
    });
    const u = userEvent.setup();
    renderWithProviders(<AccountPage />);
    await screen.findByText("Phòng A");
    const me = () => calls.filter((c) => c.url.endsWith("/api/auth/me")).length;
    const before = me();

    await u.type(screen.getByLabelText("Mật khẩu hiện tại"), "Password123!");
    await u.type(screen.getByLabelText("Mật khẩu mới"), "MatKhauMoi1");
    await u.type(screen.getByLabelText("Nhập lại mật khẩu mới"), "MatKhauMoi1");
    await u.click(screen.getByRole("button", { name: "Đổi mật khẩu" }));
    expect(await screen.findByText(/Đã đổi mật khẩu/)).toBeInTheDocument();
    await waitFor(() => expect(me()).toBeGreaterThan(before));
    expect(screen.getByLabelText("Mật khẩu hiện tại")).toHaveValue("");
  });
});
