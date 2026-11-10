import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { mockFetch, renderWithProviders, SESSION } from "@/test/utils";

import { AnalyticsPage } from "./AnalyticsPage";

// jsdom không có canvas: thay biểu đồ bằng phần tử đơn giản
vi.mock("react-chartjs-2", () => ({
  Line: (p: { "aria-label"?: string }) => <div role="img" aria-label={p["aria-label"]} />,
  Bar: (p: { "aria-label"?: string }) => <div role="img" aria-label={p["aria-label"]} />,
}));

const ROW = {
  uploads: 3,
  pages_uploaded: 5,
  ocr_edits: 1,
  submits: 0,
  approvals: 0,
  rejections: 0,
  publishes: 1,
  borrow_requests: 0,
  downloads: 2,
  jobs_completed: 3,
  jobs_failed: 1,
  lead_hours_sum: 10,
  published_docs: 1,
  job_failure_rate: 25,
  avg_lead_hours: 10,
};

describe("AnalyticsPage (FR-17)", () => {
  it("hiện chỉ số tổng, biểu đồ, bảng theo phòng ban/người dùng và link xuất CSV theo bộ lọc", async () => {
    const user = userEvent.setup();
    mockFetch({
      "GET /api/auth/me": { body: { ...SESSION, roles: ["ADMIN"] } },
      "GET /api/departments": { body: [{ id: 1, code: "A", name: "Phòng A" }] },
      "GET /api/users": { body: { items: [], total: 0, page: 1, page_size: 20 } },
      "GET /api/admin/analytics": {
        body: {
          granularity: "day",
          date_from: "2026-11-01",
          date_to: "2026-11-10",
          series: [{ period: "2026-11-10", ...ROW }],
          by_user: [
            { user_id: "u1", username: "officer", full_name: "Nhân viên A", department_name: "Phòng A", ...ROW },
          ],
          by_department: [{ department_id: 1, department_name: "Phòng A", ...ROW }],
          totals: ROW,
        },
      },
    });
    renderWithProviders(<AnalyticsPage />);
    expect(await screen.findByText("25%")).toBeInTheDocument();
    expect(screen.getByText("10 giờ")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Biểu đồ xu hướng" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "Phòng A" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Người dùng" }));
    expect(screen.getByRole("cell", { name: "Nhân viên A" })).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Gom theo"), "month");
    const link = screen.getByRole("link", { name: /Xuất CSV/ });
    expect(link.getAttribute("href")).toContain("granularity=month");
  });
});
