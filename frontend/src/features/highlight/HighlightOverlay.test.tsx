import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { mockFetch, renderWithProviders, SESSION } from "@/test/utils";

import { HighlightOverlay } from "./HighlightOverlay";

const props = { documentId: "d1", pageNumber: 2, imageWidth: 1000, imageHeight: 800, scale: 0.5, query: "cong ty" };

describe("Highlight (P2-02)", () => {
  it("vẽ mọi lần xuất hiện theo tỉ lệ ảnh và chuyển qua lại", async () => {
    const calls = mockFetch({
      "GET /api/auth/me": { body: SESSION },
      "GET /api/documents/d1/pages/2/highlights": {
        body: {
          page_number: 2,
          width: 1000,
          height: 800,
          total: 2,
          reason: null,
          boxes: [
            { x: 100, y: 200, w: 300, h: 40, line: 1 },
            { x: 500, y: 600, w: 80, h: 40, line: 5 },
          ],
        },
      },
    });
    renderWithProviders(<HighlightOverlay {...props} />);
    const boxes = await screen.findAllByTestId("highlight-box");
    expect(boxes).toHaveLength(2);
    expect(boxes[0]).toHaveStyle({ left: "50px", top: "100px", width: "150px", height: "20px" });
    expect(screen.getByText(/1\/2/)).toBeInTheDocument();
    await userEvent.click(screen.getByLabelText("Kết quả sau"));
    expect(screen.getByText(/2\/2/)).toBeInTheDocument();
    expect(calls.find((c) => c.url.includes("highlights"))?.url).toContain("q=cong+ty");
  });

  it("trang đã sửa: không vẽ, báo rõ lý do", async () => {
    mockFetch({
      "GET /api/auth/me": { body: SESSION },
      "GET /api/documents/d1/pages/2/highlights": {
        body: { page_number: 2, width: 1000, height: 800, total: 0, reason: "text_modified", boxes: [] },
      },
    });
    renderWithProviders(<HighlightOverlay {...props} />);
    expect(await screen.findByText(/đã được chỉnh sửa/)).toBeInTheDocument();
    expect(screen.queryAllByTestId("highlight-box")).toHaveLength(0);
  });

  it("không có từ khóa: không gọi API", () => {
    const calls = mockFetch({ "GET /api/auth/me": { body: SESSION } });
    renderWithProviders(<HighlightOverlay {...props} query=" " />);
    expect(calls.some((c) => c.url.includes("highlights"))).toBe(false);
  });
});
