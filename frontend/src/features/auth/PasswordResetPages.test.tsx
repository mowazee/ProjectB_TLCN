import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { describe, expect, it } from "vitest";

import { mockFetch, renderWithProviders } from "@/test/utils";

import { LoginPage } from "./LoginPage";
import { ForgotPasswordPage, ResetPasswordPage } from "./PasswordResetPages";

const NO_SESSION = { status: 401, body: { error: { code: "UNAUTHENTICATED", message: "x" } } };
const OPTIONS = { body: { password_reset: true, password_reset_ttl_minutes: 30 } };

function resetRoute(token: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/reset-password/:token" element={<ResetPasswordPage />} />
    </Routes>,
    { route: `/reset-password/${token}` },
  );
}

describe("Đăng nhập: khóa tài khoản và quên mật khẩu (v0.17)", () => {
  it("sai mật khẩu: hiện cảnh báo khóa sau 5 lần và link Quên mật khẩu khi đã cấu hình email", async () => {
    mockFetch({
      "GET /api/auth/me": NO_SESSION,
      "GET /api/auth/options": OPTIONS,
      "POST /api/auth/login": {
        status: 401,
        body: {
          error: {
            code: "INVALID_CREDENTIALS",
            message:
              "Tên đăng nhập hoặc mật khẩu không đúng, lưu ý tài khoản sẽ bị khóa nếu nhập sai mật khẩu quá 5 lần",
          },
        },
      },
    });
    const user = userEvent.setup();
    renderWithProviders(<LoginPage />, { route: "/login" });
    expect(await screen.findByRole("link", { name: "Quên mật khẩu?" })).toHaveAttribute("href", "/forgot-password");
    await user.type(screen.getByLabelText("Tên đăng nhập hoặc email"), "officer");
    await user.type(screen.getByLabelText("Mật khẩu"), "sai");
    await user.click(screen.getByRole("button", { name: "Đăng nhập" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("sẽ bị khóa nếu nhập sai mật khẩu quá 5 lần");
  });

  it("tài khoản bị khóa: báo liên hệ Quản trị viên và gợi ý dùng Quên mật khẩu", async () => {
    mockFetch({
      "GET /api/auth/me": NO_SESSION,
      "GET /api/auth/options": OPTIONS,
      "POST /api/auth/login": {
        status: 401,
        body: { error: { code: "ACCOUNT_LOCKED", message: "Tài khoản đã bị khóa, vui lòng liên hệ Quản trị viên" } },
      },
    });
    const user = userEvent.setup();
    renderWithProviders(<LoginPage />, { route: "/login" });
    await user.type(await screen.findByLabelText("Tên đăng nhập hoặc email"), "officer");
    await user.type(screen.getByLabelText("Mật khẩu"), "sai");
    await user.click(screen.getByRole("button", { name: "Đăng nhập" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("liên hệ Quản trị viên");
    expect(await screen.findByRole("link", { name: "Quên mật khẩu" })).toBeInTheDocument();
  });

  it("chưa cấu hình email: không hiện link Quên mật khẩu", async () => {
    mockFetch({
      "GET /api/auth/me": NO_SESSION,
      "GET /api/auth/options": { body: { password_reset: false, password_reset_ttl_minutes: 30 } },
    });
    renderWithProviders(<LoginPage />, { route: "/login" });
    await screen.findByLabelText("Tên đăng nhập hoặc email");
    expect(screen.queryByRole("link", { name: "Quên mật khẩu?" })).toBeNull();
  });

  it("Quên mật khẩu: gửi tên đăng nhập, hiện thông báo kiểm tra email", async () => {
    const calls = mockFetch({
      "GET /api/auth/me": NO_SESSION,
      "GET /api/auth/options": OPTIONS,
      "POST /api/auth/forgot-password": { status: 202, body: { message: "Nếu thông tin khớp, email đã được gửi." } },
    });
    const user = userEvent.setup();
    renderWithProviders(<ForgotPasswordPage />, { route: "/forgot-password" });
    expect(await screen.findByText(/hiệu lực 30 phút/)).toBeInTheDocument();
    await user.type(screen.getByLabelText("Tên đăng nhập hoặc email"), " officer ");
    await user.click(screen.getByRole("button", { name: "Gửi link khôi phục" }));
    expect(await screen.findByRole("status")).toHaveTextContent("email đã được gửi");
    expect(calls.find((c) => c.url.endsWith("/forgot-password"))?.body).toEqual({ login: "officer" });
  });

  it("Quên mật khẩu: không gửi được email thì báo liên hệ Quản trị viên", async () => {
    mockFetch({
      "GET /api/auth/me": NO_SESSION,
      "GET /api/auth/options": OPTIONS,
      "POST /api/auth/forgot-password": {
        status: 503,
        body: {
          error: {
            code: "EMAIL_SEND_FAILED",
            message: "Không gửi được email khôi phục mật khẩu, vui lòng liên hệ Quản trị viên",
          },
        },
      },
    });
    const user = userEvent.setup();
    renderWithProviders(<ForgotPasswordPage />, { route: "/forgot-password" });
    await user.type(await screen.findByLabelText("Tên đăng nhập hoặc email"), "nhanvien");
    await user.click(screen.getByRole("button", { name: "Gửi link khôi phục" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Không gửi được email khôi phục mật khẩu, vui lòng liên hệ Quản trị viên",
    );
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("Đặt lại mật khẩu: kiểm nhập lại khớp, gửi mật khẩu mới, báo đã mở khóa", async () => {
    const calls = mockFetch({
      "GET /api/auth/me": NO_SESSION,
      "GET /api/auth/reset-password/tok": { body: { username: "officer" } },
      "POST /api/auth/reset-password/tok": { body: { message: "ok", reactivated: true } },
    });
    const user = userEvent.setup();
    resetRoute("tok");
    expect(await screen.findByText("officer")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Mật khẩu mới"), "MatKhau@2026");
    await user.type(screen.getByLabelText("Nhập lại mật khẩu mới"), "Khac@2026");
    await user.click(screen.getByRole("button", { name: "Đặt mật khẩu mới" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("không khớp");
    await user.clear(screen.getByLabelText("Nhập lại mật khẩu mới"));
    await user.type(screen.getByLabelText("Nhập lại mật khẩu mới"), "MatKhau@2026");
    await user.click(screen.getByRole("button", { name: "Đặt mật khẩu mới" }));
    expect(await screen.findByRole("status")).toHaveTextContent("mở khóa tài khoản");
    const post = calls.find((c) => c.method === "POST" && c.url.includes("/reset-password/"));
    expect(post?.body).toEqual({ new_password: "MatKhau@2026" });
  });

  it("link hết hạn hoặc đã dùng: báo lỗi và cho gửi lại link", async () => {
    mockFetch({
      "GET /api/auth/me": NO_SESSION,
      "GET /api/auth/reset-password/old": {
        status: 410,
        body: {
          error: { code: "RESET_LINK_INVALID", message: "Link khôi phục mật khẩu không hợp lệ hoặc đã hết hạn" },
        },
      },
    });
    resetRoute("old");
    expect(await screen.findByRole("alert")).toHaveTextContent("đã hết hạn");
    expect(screen.getByRole("link", { name: "Gửi lại link khôi phục" })).toHaveAttribute("href", "/forgot-password");
    expect(screen.queryByLabelText("Mật khẩu mới")).toBeNull();
  });
});
