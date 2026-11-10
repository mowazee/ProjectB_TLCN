import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { PageDetail } from "@/shared/api/types";
import { mockFetch, renderWithProviders, SESSION } from "@/test/utils";

import { EditorForm } from "./EditorPage";

const PAGE: PageDetail = {
  document_id: "d1",
  page_number: 1,
  total_pages: 1,
  width: 100,
  height: 100,
  ocr_status: "completed",
  engine_version: "paddleocr 3",
  is_text_layer: false,
  confidence: "90",
  raw_text: "Hop dong",
  effective_text: "Hop dong",
  version: 0,
  edited_by: null,
  edited_at: null,
  boxes: [],
  can_edit: true,
};

describe("OCR Editor (FR-05, SDD mục 13: 409 giữ draft)", () => {
  it("409 VERSION_CONFLICT giữ nguyên bản nháp và cho tải bản mới để lưu đè", async () => {
    let attempts = 0;
    const calls = mockFetch({
      "GET /api/auth/me": { body: SESSION },
      "PUT /api/documents/d1/pages/1/correction": () => {
        attempts += 1;
        return attempts === 1
          ? {
              status: 409,
              body: { error: { code: "VERSION_CONFLICT", message: "conflict", details: { current_version: 1 } } },
            }
          : { body: { version: 2, base_version: 1, edited_by: null, edited_at: "2026-10-04T00:00:00Z" } };
      },
      "GET /api/documents/d1/pages/1": { body: { ...PAGE, version: 1, effective_text: "Hợp đồng (người khác)" } },
    });
    const user = userEvent.setup();
    renderWithProviders(<EditorForm documentId="d1" page={PAGE} />);

    const box = screen.getByLabelText("Nội dung OCR");
    await user.clear(box);
    await user.type(box, "Hợp đồng của tôi");
    await user.click(screen.getByRole("button", { name: /Lưu phiên bản mới/ }));

    expect(await screen.findByText(/đã được người khác cập nhật/)).toBeInTheDocument();
    expect(screen.getByLabelText("Nội dung OCR")).toHaveValue("Hợp đồng của tôi"); // draft giữ nguyên

    await user.click(screen.getByRole("button", { name: /Tải bản mới nhất/ }));
    expect(await screen.findByText("Hợp đồng (người khác)")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Giữ bản nháp của tôi/ }));
    await user.click(screen.getByRole("button", { name: /Lưu phiên bản mới/ }));

    await waitFor(() => expect(attempts).toBe(2));
    const puts = calls.filter((c) => c.method === "PUT");
    expect(puts[0].body).toEqual({ corrected_text: "Hợp đồng của tôi", base_version: 0 });
    expect(puts[1].body).toEqual({ corrected_text: "Hợp đồng của tôi", base_version: 1 });
  });
});

describe("OCR Editor mức 1 (FR-05, SDD v0.13)", () => {
  const P2: PageDetail = {
    ...PAGE,
    raw_text: "CONG HOA\nQuyet dinh",
    effective_text: "CONG HOA\nQuyet dinh",
    boxes: [
      { text: "CONG HOA", score: 0.97, box: [1, 2, 30, 8] },
      { text: "Quyet dinh", score: 0.4, box: [1, 20, 40, 8] },
    ],
  };

  it("thay tất cả, hoàn tác, xem khác biệt, tới dòng tin cậy thấp", async () => {
    window.localStorage.clear();
    const user = userEvent.setup();
    mockFetch({ "GET /api/auth/me": { body: SESSION } });
    const boxes: (number[] | null)[] = [];
    renderWithProviders(<EditorForm documentId="d1" page={P2} onActiveBox={(b) => boxes.push(b)} />);
    const area = await screen.findByLabelText("Nội dung OCR");
    expect(screen.getByText(/1 dòng có độ tin cậy thấp/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Tới dòng tin cậy thấp kế tiếp" }));
    expect(boxes.at(-1)).toEqual([1, 20, 40, 8]);
    await user.type(screen.getByLabelText("Tìm"), "quyet");
    await user.type(screen.getByLabelText("Thay bằng"), "Quyết");
    await user.click(screen.getByRole("button", { name: "Thay tất cả (1)" }));
    expect(area).toHaveValue("CONG HOA\nQuyết dinh");
    await user.click(screen.getByRole("button", { name: "Xem khác biệt với bản OCR" }));
    expect(screen.getByText("- Quyet dinh")).toBeInTheDocument();
    expect(screen.getByText("+ Quyết dinh")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Hoàn tác (Ctrl+Z)" }));
    expect(area).toHaveValue("CONG HOA\nQuyet dinh");
  });

  it("nháp tự lưu trong trình duyệt được đề nghị khôi phục", async () => {
    window.localStorage.setItem("ocr-draft:d1:1:0", "CONG HOA\nBan nhap");
    const user = userEvent.setup();
    mockFetch({ "GET /api/auth/me": { body: SESSION } });
    renderWithProviders(<EditorForm documentId="d1" page={P2} />);
    await user.click(await screen.findByRole("button", { name: "Khôi phục bản nháp" }));
    expect(screen.getByLabelText("Nội dung OCR")).toHaveValue("CONG HOA\nBan nhap");
    window.localStorage.clear();
  });
});
