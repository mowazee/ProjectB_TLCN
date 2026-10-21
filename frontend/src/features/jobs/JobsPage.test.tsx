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
    const queued = within(screen.getByText("OCR chữ viết tay").closest("tr")!);
    expect(queued.queryByRole("button", { name: /Chạy lại/ })).toBeNull();
    expect(queued.getByRole("button", { name: /Dừng/ })).toBeInTheDocument(); // FR-04 v0.10
    await u.click(within(failed).getByRole("button", { name: /Chạy lại/ }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.url.endsWith("/j2/retry"))).toBe(true));
  });

  it("Dừng job đang xử lý: hỏi xác nhận rồi gọi API, hiển thị Đã dừng", async () => {
    let cancelled = false;
    const calls = mockFetch({
      "GET /api/auth/me": { body: SESSION },
      "GET /api/jobs": () => ({
        body: {
          items: [
            cancelled
              ? job("j1", { status: "failed", error_code: "CANCELLED", error_message: "Đã dừng theo yêu cầu." })
              : job("j1", { status: "processing", progress: 40 }),
          ],
          total: 1,
          page: 1,
          page_size: 20,
        },
      }),
      "POST /api/jobs/j1/cancel": () => {
        cancelled = true;
        return { body: job("j1", { status: "failed", error_code: "CANCELLED" }) };
      },
    });
    const u = userEvent.setup();
    renderWithProviders(<JobsPage />, { route: "/jobs" });
    await u.click(await screen.findByRole("button", { name: /Dừng/ }));
    const dialog = screen.getByRole("dialog", { name: "Dừng xử lý tài liệu?" });
    expect(within(dialog).getByText(/dừng sau trang đang xử lý/)).toBeInTheDocument();
    await u.click(within(dialog).getByRole("button", { name: /Dừng xử lý/ }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.url.endsWith("/j1/cancel"))).toBe(true));
    expect(await screen.findByText("Đã dừng")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
