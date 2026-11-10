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
});
