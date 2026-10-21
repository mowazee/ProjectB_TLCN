import { fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { mockFetch, renderWithProviders, SESSION } from "@/test/utils";

import { UploadPage } from "./UploadPage";

const CATEGORIES = [
  { id: 1, name: "Hợp đồng", code: "HOP-DONG", is_active: true, is_system: false },
  { id: 9, name: "Chưa phân loại", code: "CHUA-PHAN-LOAI", is_active: true, is_system: true },
];

function render(features: string[]) {
  const calls = mockFetch({
    "GET /api/auth/me": { body: { ...SESSION, features } },
    "GET /api/categories": { body: CATEGORIES },
    "POST /api/documents": { status: 201, body: { document_id: "d1", job_id: "j1" } },
    "GET /api/jobs/j1": { body: { id: "j1", status: "queued", progress: 0 } },
  });
  renderWithProviders(<UploadPage />, { route: "/documents/upload" });
  return calls;
}

const sent = (calls: ReturnType<typeof mockFetch>) => {
  const call = calls.find((c) => c.method === "POST" && c.url.startsWith("/api/documents"));
  return call?.body as FormData;
};

// jsdom không coi file do user.upload gán là đã chọn khi kiểm tra required: gửi form trực tiếp
const submit = () =>
  fireEvent.submit(screen.getByRole("button", { name: /Tải lên/ }).closest("form") as HTMLFormElement);

async function pickFile(user: ReturnType<typeof userEvent.setup>) {
  await user.upload(screen.getByLabelText("File"), new File(["%PDF-1.4"], "a.pdf", { type: "application/pdf" }));
}

describe("UploadPage - cách chọn danh mục (D-10)", () => {
  it("mặc định Danh mục gợi ý: không hiện ô chọn, gửi category_mode=auto", async () => {
    const user = userEvent.setup();
    const calls = render(["classification"]);
    const auto = await screen.findByRole("radio", { name: /Danh mục gợi ý/ });
    expect(auto).toHaveAttribute("aria-checked", "true");
    expect(screen.queryByLabelText("Chọn danh mục")).not.toBeInTheDocument();

    await pickFile(user);
    submit();
    expect(await screen.findByText(/Danh mục sẽ được tự chọn sau khi OCR xong/)).toBeInTheDocument();
    const form = sent(calls);
    expect(form.get("category_mode")).toBe("auto");
    expect(form.get("category_id")).toBeNull();
  });

  it("Tôi chọn danh mục: hiện ô chọn, không có danh mục hệ thống", async () => {
    const user = userEvent.setup();
    const calls = render(["classification"]);
    await user.click(await screen.findByRole("radio", { name: /Tôi chọn danh mục/ }));
    const select = screen.getByLabelText("Chọn danh mục");
    expect(screen.getByRole("option", { name: "Hợp đồng" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Chưa phân loại" })).not.toBeInTheDocument();

    await pickFile(user);
    await user.selectOptions(select, "1");
    submit();
    await screen.findByText("Đã tải lên thành công.");
    const form = sent(calls);
    expect(form.get("category_mode")).toBe("user");
    expect(form.get("category_id")).toBe("1");
  });

  it("phân loại tự động tắt: chỉ có ô chọn danh mục", async () => {
    const user = userEvent.setup();
    const calls = render([]);
    const select = await screen.findByLabelText("Danh mục");
    expect(screen.queryByRole("radio")).not.toBeInTheDocument();
    await screen.findByRole("option", { name: "Hợp đồng" });
    await pickFile(user);
    await user.selectOptions(select, "1");
    submit();
    await screen.findByText("Đã tải lên thành công.");
    expect(sent(calls).get("category_mode")).toBe("user");
  });
});
