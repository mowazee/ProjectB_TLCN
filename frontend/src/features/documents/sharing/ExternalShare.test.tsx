import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { describe, expect, it } from "vitest";

import type { DocumentOut } from "@/shared/api/types";
import { mockFetch, renderWithProviders, SESSION } from "@/test/utils";

import { ExternalShareDialog } from "./ExternalShareDialog";
import { PublicSharePage } from "./PublicSharePage";

const DOC = { id: "d1", title: "Quyết định 12" } as DocumentOut;
const LINK = {
  id: "l1",
  recipient_email: "khach@example.com",
  allow_download: true,
  expires_at: "2026-11-11T03:00:00Z",
  revoked_at: null,
  email_status: "sent",
  created_by: "Nhân viên A",
  created_at: "2026-11-10T03:00:00Z",
  last_accessed_at: null,
  access_count: 2,
  status: "active",
};

describe("ExternalShareDialog (FR-18)", () => {
  it("gửi link qua email, hiện link một lần và danh sách link có nút thu hồi", async () => {
    const user = userEvent.setup();
    const calls = mockFetch({
      "GET /api/auth/me": { body: SESSION },
      "GET /api/documents/d1/external-shares": { body: { enabled: true, max_hours: 24, items: [LINK] } },
      "POST /api/documents/d1/external-shares": {
        status: 201,
        body: { link: LINK, url: "http://127.0.0.1:8080/s/abcdefghijklmnopqrstuvwxyz" },
      },
    });
    renderWithProviders(<ExternalShareDialog doc={DOC} onClose={() => {}} />);
    expect(await screen.findByRole("cell", { name: /khach@example.com/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Thu hồi" })).toBeInTheDocument();
    await user.type(screen.getByLabelText("Email người nhận"), "doitac@example.com");
    await user.click(screen.getByLabelText(/Cho phép tải/));
    await user.click(screen.getByRole("button", { name: /Gửi link qua email/ }));
    expect(await screen.findByText(/s\/abcdefghijklmnopqrstuvwxyz/)).toBeInTheDocument();
    const post = calls.find((c) => c.method === "POST");
    expect(post?.body).toEqual({ recipient_email: "doitac@example.com", expires_in_hours: 24, allow_download: true });
  });

  it("chưa cấu hình SMTP thì báo rõ, không có form", async () => {
    mockFetch({
      "GET /api/auth/me": { body: SESSION },
      "GET /api/documents/d1/external-shares": { body: { enabled: false, max_hours: 24, items: [] } },
    });
    renderWithProviders(<ExternalShareDialog doc={DOC} onClose={() => {}} />);
    expect(await screen.findByText(/chưa cấu hình gửi email/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Email người nhận")).toBeNull();
  });
});

describe("PublicSharePage (FR-18)", () => {
  const route = "/s/tok-0123456789abcdefghij";
  const base = "/api/public/shares/tok-0123456789abcdefghij";
  const render = () =>
    renderWithProviders(
      <Routes>
        <Route path="/s/:token" element={<PublicSharePage />} />
      </Routes>,
      { route },
    );

  it("chưa xác thực: gửi mã và nhập OTP", async () => {
    const user = userEvent.setup();
    const calls = mockFetch({
      [`GET ${base}`]: {
        body: {
          title: "Quyết định 12",
          expires_at: "2026-11-11T03:00:00Z",
          recipient: "kh***@example.com",
          allow_download: false,
          verified: false,
          pages: [],
          attachments: [],
        },
      },
      [`POST ${base}/otp`]: { body: { sent_to: "kh***@example.com" } },
      [`POST ${base}/verify`]: { status: 204, body: null },
    });
    render();
    await user.click(await screen.findByRole("button", { name: "Gửi mã xác thực" }));
    expect(await screen.findByText(/Đã gửi mã tới/)).toBeInTheDocument();
    await user.type(screen.getByLabelText("Mã xác thực"), "123456");
    await user.click(screen.getByRole("button", { name: "Xác nhận" }));
    expect(calls.find((c) => c.url.endsWith("/verify"))?.body).toEqual({ code: "123456" });
  });

  it("link hết hiệu lực hiện thông báo", async () => {
    mockFetch({ [`GET ${base}`]: { status: 410, body: { error: { code: "SHARE_LINK_GONE", message: "x" } } } });
    render();
    expect(await screen.findByText("Link không còn hiệu lực")).toBeInTheDocument();
  });

  it("đã xác thực: xem trang, tải file khi được phép", async () => {
    mockFetch({
      [`GET ${base}`]: {
        body: {
          title: "Quyết định 12",
          expires_at: "2026-11-11T03:00:00Z",
          recipient: "kh***@example.com",
          allow_download: true,
          verified: true,
          file_name: "qd.pdf",
          pages: [{ page_number: 1, width: 100, height: 140 }],
          attachments: [{ id: "a1", file_name: "phu-luc.docx", bytes: 2048 }],
        },
      },
    });
    render();
    expect(await screen.findByRole("img", { name: "Trang 1" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Tải file gốc/ }).getAttribute("href")).toBe(`${base}/file`);
    expect(screen.getByRole("link", { name: "phu-luc.docx" }).getAttribute("href")).toBe(`${base}/attachments/a1`);
  });
});
