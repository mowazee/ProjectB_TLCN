import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { mockFetch, renderWithProviders, SESSION } from "@/test/utils";

import { GuidePage } from "./GuidePage";

describe("GuidePage", () => {
  it("trang Hướng dẫn sử dụng trống", async () => {
    mockFetch({ "GET /api/auth/me": { body: SESSION } });
    renderWithProviders(<GuidePage />);
    expect(await screen.findByRole("heading", { name: "Hướng dẫn sử dụng" })).toBeInTheDocument();
    expect(screen.getByText(/Chưa có tài liệu hướng dẫn/)).toBeInTheDocument();
  });
});
