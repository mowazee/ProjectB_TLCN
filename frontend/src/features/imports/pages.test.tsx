import { fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { mockFetch, renderWithProviders, SESSION } from "@/test/utils";

import { ImportPage, ImportReportPage } from "./pages";

const CATEGORIES = [
  { id: 1, name: "Hợp đồng", code: "HOP-DONG", is_active: true, is_system: false },
  { id: 9, name: "Chưa phân loại", code: "CHUA-PHAN-LOAI", is_active: true, is_system: true },
];

function renderImport(features: string[]) {
  const calls = mockFetch({
    "GET /api/auth/me": { body: { ...SESSION, features } },
    "GET /api/categories": { body: CATEGORIES },
    "POST /api/imports": { status: 202, body: { job_id: "j1", status: "queued", files: 1 } },
    "GET /api/imports/j1": { body: { job_id: "j1", status: "queued", progress: 0, files: [], total: 1 } },
  });
  renderWithProviders(
    <Routes>
      <Route path="/imports" element={<ImportPage />} />
      <Route path="/imports/:jobId" element={<p>Báo cáo lô</p>} />
    </Routes>,
    { route: "/imports" },
  );
  return calls;
}

const sentForm = (calls: ReturnType<typeof mockFetch>) =>
  calls.find((c) => c.method === "POST" && c.url.startsWith("/api/imports"))?.body as FormData;

// jsdom không coi file do user.upload gán là đã chọn khi kiểm tra required: gửi form trực tiếp
const submit = () =>
  fireEvent.submit(screen.getByRole("button", { name: "Bắt đầu nhập" }).closest("form") as HTMLFormElement);

describe("ImportPage - danh mục cho cả lô (P2-08, D-10)", () => {
  it("mặc định Danh mục gợi ý: không có ô chọn danh mục, gửi category_mode=auto", async () => {
    const user = userEvent.setup();
    const calls = renderImport(["imports", "classification"]);
    expect(await screen.findByRole("radio", { name: /Danh mục gợi ý/ })).toHaveAttribute("aria-checked", "true");
    expect(screen.queryByLabelText("Chọn danh mục")).not.toBeInTheDocument();
    await user.upload(screen.getByLabelText(/Các file/), new File(["%PDF"], "a.pdf", { type: "application/pdf" }));
    submit();
    expect(await screen.findByText("Báo cáo lô")).toBeInTheDocument();
    const form = sentForm(calls);
    expect(form.get("category_mode")).toBe("auto");
    expect(form.get("category_id")).toBeNull();
  });

  it("Tôi chọn danh mục: ô chọn không có danh mục hệ thống; phân loại tắt thì chỉ có ô chọn", async () => {
    const user = userEvent.setup();
    renderImport(["imports", "classification"]);
    await user.click(await screen.findByRole("radio", { name: /Tôi chọn danh mục/ }));
    expect(screen.getByLabelText("Chọn danh mục")).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Chưa phân loại" })).not.toBeInTheDocument();
  });

  it("phân loại tắt: không có thẻ chọn, gửi category_mode=user", async () => {
    const user = userEvent.setup();
    const calls = renderImport(["imports"]);
    const select = await screen.findByLabelText("Danh mục");
    expect(screen.queryByRole("radio")).not.toBeInTheDocument();
    await screen.findByRole("option", { name: "Hợp đồng" });
    await user.upload(screen.getByLabelText(/Các file/), new File(["%PDF"], "a.pdf", { type: "application/pdf" }));
    await user.selectOptions(select, "1");
    submit();
    await screen.findByText("Báo cáo lô");
    expect(sentForm(calls).get("category_mode")).toBe("user");
    expect(sentForm(calls).get("category_id")).toBe("1");
  });

  it("tải file metadata.csv mẫu có đủ cột và mã danh mục thật", async () => {
    const user = userEvent.setup();
    renderImport(["imports", "classification"]);
    await screen.findByRole("radio", { name: /Danh mục gợi ý/ });
    await screen.findByText(/Thông tin riêng cho từng file/);
    let blob: Blob | undefined;
    URL.createObjectURL = vi.fn((b: Blob) => {
      blob = b;
      return "blob:x";
    });
    URL.revokeObjectURL = vi.fn();
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    await vi.waitFor(() => expect(screen.getByRole("button", { name: /Tải file mẫu/ })).toBeEnabled());
    await user.click(screen.getByRole("button", { name: /Tải file mẫu/ }));
    expect(click).toHaveBeenCalled();
    const bytes = new Uint8Array(await blob!.arrayBuffer());
    expect([...bytes.slice(0, 3)]).toEqual([0xef, 0xbb, 0xbf]); // BOM: Excel mở đúng tiếng Việt
    const text = await blob!.text(); // text() bỏ BOM khi giải mã
    expect(text.startsWith("file_name,title,category,document_code")).toBe(true);
    expect(text).toContain(",HOP-DONG,");
  });
});

describe("ImportReportPage - danh mục từng file", () => {
  it("hiện danh mục hiện tại và nguồn của từng tài liệu đã nhập", async () => {
    mockFetch({
      "GET /api/auth/me": { body: SESSION },
      "GET /api/imports/j1": {
        body: {
          job_id: "j1",
          status: "completed",
          progress: 100,
          error_code: null,
          queued_at: "2026-10-23T00:00:00Z",
          finished_at: "2026-10-23T00:01:00Z",
          total: 3,
          imported: 2,
          errors: 1,
          files: [
            {
              name: "a.pdf",
              status: "imported",
              document_id: "d1",
              category_name: "Hợp đồng",
              category_source: "auto",
            },
            {
              name: "b.pdf",
              status: "imported",
              document_id: "d2",
              category_name: "Chưa phân loại",
              category_source: "pending",
            },
            { name: "c.pdf", status: "error", code: "CATEGORY_NOT_FOUND", message: "Không có danh mục mã 'X'" },
          ],
        },
      },
    });
    renderWithProviders(
      <Routes>
        <Route path="/imports/:jobId" element={<ImportReportPage />} />
      </Routes>,
      { route: "/imports/j1" },
    );
    const row = async (name: string) => (await screen.findByRole("cell", { name })).closest("tr") as HTMLElement;
    expect(within(await row("a.pdf")).getByText("Tự động")).toBeInTheDocument();
    expect(within(await row("a.pdf")).getByText("Hợp đồng")).toBeInTheDocument();
    expect(within(await row("b.pdf")).getByText("Chờ phân loại")).toBeInTheDocument();
    expect(within(await row("c.pdf")).getByText("—")).toBeInTheDocument();
  });
});
