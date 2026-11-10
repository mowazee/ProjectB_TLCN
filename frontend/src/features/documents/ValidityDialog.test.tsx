import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { DocumentOut } from "@/shared/api/types";
import { formatValidity } from "@/shared/lib/validity";
import { mockFetch, renderWithProviders, SESSION } from "@/test/utils";

import { ValidityDialog } from "./ValidityDialog";

const DOC = {
  id: "d1",
  title: "Quyết định 1",
  approval_status: "published",
  validity_status: "effective",
  valid_until: null,
} as DocumentOut;

describe("ValidityDialog (FR-19)", () => {
  it("tài liệu đã xuất bản: bắt buộc lý do trước khi lưu", async () => {
    const user = userEvent.setup();
    const calls = mockFetch({
      "GET /api/auth/me": { body: { ...SESSION, features: ["workflow"] } },
      "PUT /api/documents/d1/validity": { body: { ...DOC, validity_status: "expired" } },
    });
    renderWithProviders(<ValidityDialog doc={DOC} onClose={() => {}} />);
    await user.click(await screen.findByLabelText("Hết hiệu lực"));
    const save = screen.getByRole("button", { name: "Lưu" });
    expect(save).toBeDisabled();
    await user.type(await screen.findByLabelText(/Lý do thay đổi \(bắt buộc/), "Đã có văn bản thay thế");
    await user.click(save);
    expect(calls.find((c) => c.method === "PUT")?.body).toEqual({
      validity_status: "expired",
      valid_until: null,
      reason: "Đã có văn bản thay thế",
    });
  });

  it("nhãn hiệu lực", () => {
    expect(formatValidity("effective_until", "2026-12-31")).toBe("Còn hiệu lực đến 31/12/2026");
    expect(formatValidity("expired", null)).toBe("Hết hiệu lực");
    expect(formatValidity("unspecified")).toBe("Không quy định");
  });
});
