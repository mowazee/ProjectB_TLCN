import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { mockFetch, renderWithProviders, SESSION } from "@/test/utils";

import { SettingsPage } from "./SettingsPage";

describe("SettingsPage - cấu hình thời gian lưu trữ (FR-14)", () => {
  it("hiện giá trị hiện tại và gửi PUT khi lưu", async () => {
    const user = userEvent.setup();
    const calls = mockFetch({
      "GET /api/auth/me": { body: { ...SESSION, roles: ["ADMIN"] } },
      "GET /api/admin/settings": { body: { trash_retention_days: 30, audit_retention_days: 365 } },
      "PUT /api/admin/settings": { body: { trash_retention_days: 14, audit_retention_days: 365 } },
    });
    renderWithProviders(<SettingsPage />);
    const trash = await screen.findByLabelText("Giữ tài liệu trong thùng rác (ngày)");
    expect(trash).toHaveValue(30);
    expect(screen.getByRole("button", { name: "Lưu cấu hình" })).toBeDisabled();
    await user.clear(trash);
    await user.type(trash, "14");
    await user.click(screen.getByRole("button", { name: "Lưu cấu hình" }));
    const put = calls.find((c) => c.method === "PUT");
    expect(put?.body).toEqual({ trash_retention_days: 14, audit_retention_days: 365 });
  });
});
