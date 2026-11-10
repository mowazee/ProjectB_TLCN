import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { mockFetch, renderWithProviders, SESSION } from "@/test/utils";

import { AuditPage } from "./AuditPage";

describe("AuditPage - bộ lọc theo tên (v0.15)", () => {
  it("lọc theo tên người dùng, tên tài liệu, hành động gần đúng", async () => {
    const user = userEvent.setup();
    const calls = mockFetch({
      "GET /api/auth/me": { body: SESSION },
      "GET /api/audit": { body: { items: [], total: 0, page: 1, page_size: 25 } },
    });
    renderWithProviders(<AuditPage />);
    await user.type(await screen.findByLabelText("Người dùng"), "nhanvien");
    await user.type(screen.getByLabelText("Tài liệu"), "Quyết định");
    await user.type(screen.getByLabelText("Hành động"), "share");
    await vi.waitFor(() => {
      const last = calls.filter((c) => c.url.includes("/api/audit")).at(-1)!;
      expect(last.url).toContain("user=nhanvien");
      expect(new URL(last.url, "http://x").searchParams.get("document")).toBe("Quyết định");
      expect(last.url).toContain("action=share");
    });
    expect(screen.queryByPlaceholderText(/ID/)).toBeNull();
  });

  it("cột Tên tài liệu hiện tên và liên kết tới tài liệu", async () => {
    mockFetch({
      "GET /api/auth/me": { body: SESSION },
      "GET /api/audit": {
        body: {
          items: [
            {
              id: 1,
              created_at: "2026-11-11T03:00:00Z",
              user_id: null,
              user_name: "Nhân viên A",
              action: "upload_document",
              module: "documents",
              entity_type: "document",
              entity_id: "d1",
              document_id: "d1",
              document_title: "Quyết định 12",
              result: "success",
              ip_address: null,
              state_before: null,
              state_after: null,
            },
          ],
          total: 1,
          page: 1,
          page_size: 25,
        },
      },
    });
    renderWithProviders(<AuditPage />);
    expect(await screen.findByRole("columnheader", { name: "Tên tài liệu" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Quyết định 12" }).getAttribute("href")).toBe("/documents/d1");
  });
});
