import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { mockFetch, renderWithProviders, SESSION } from "@/test/utils";

import { JobsPage } from "./JobsPage";

const job = (id: string, over: Record<string, unknown>) => ({
  id,
  document_id: "d1",
  document_title: "Hợp đồng 01",
  kind: "OCR",
  queue_name: "ocr",
  status: "completed",
  progress: 100,
  attempt: 1,
  max_attempts: 3,
  error_code: null,
  error_message: null,
  result: null,
  queued_at: "2026-10-18T01:00:00Z",
  started_at: null,
  finished_at: null,
  stale: false,
  ...over,
});

describe("Trang Hàng đợi xử lý (FR-11)", () => {
  it("đánh dấu job chờ quá lâu, lọc qua query, chạy lại job lỗi", async () => {
    const calls = mockFetch({
      "GET /api/auth/me": { body: SESSION },
      "GET /api/jobs": {
        body: {
          items: [
            job("j1", { status: "queued", progress: 0, queue_name: "ocr_hw", stale: true }),
            job("j2", { status: "failed", error_code: "FILE_CORRUPT", error_message: "File bị hỏng" }),
            job("j3", { document_id: null, document_title: null, kind: "BULK_IMPORT", queue_name: "default" }),
          ],
          total: 3,
          page: 1,
          page_size: 20,
        },
      },
      "POST /api/jobs/j2/retry": { body: job("j2", { status: "queued", progress: 0 }) },
    });
    const u = userEvent.setup();
    renderWithProviders(<JobsPage />, { route: "/jobs?status=queued" });

    expect(await screen.findByText(/1 job chờ quá lâu/)).toBeInTheDocument();
    expect(screen.getByText("OCR chữ viết tay")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Báo cáo lô nhập" })).toHaveAttribute("href", "/imports/j3");
    expect(calls.find((c) => c.url.includes("/api/jobs"))?.url).toContain("status=queued");

    const failed = screen.getByText("File bị hỏng").closest("tr")!;
    expect(within(screen.getByText("OCR chữ viết tay").closest("tr")!).queryByRole("button")).toBeNull();
    await u.click(within(failed).getByRole("button", { name: /Chạy lại/ }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.url.endsWith("/j2/retry"))).toBe(true));
  });
});
