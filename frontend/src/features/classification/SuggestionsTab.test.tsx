import { useQuery } from "@tanstack/react-query";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { api } from "@/shared/api/client";
import type { DocumentOut } from "@/shared/api/types";
import { mockFetch, renderWithProviders, SESSION } from "@/test/utils";

import { SuggestionsTab } from "./SuggestionsTab";

const CATS: Record<number, string> = { 1: "Hợp đồng", 2: "Công văn", 9: "Chưa phân loại" };

/** Trang chi tiết thu gọn: tài liệu lấy từ query ["documents", ...] như DocumentDetailPage. */
function Host() {
  const doc = useQuery({
    queryKey: ["documents", "detail", "d1"],
    queryFn: () => api<DocumentOut>("/api/documents/d1"),
  });
  if (!doc.data) return null;
  return (
    <>
      {/* như trang chi tiết tự hỏi lại tài liệu khi job OCR đang chạy */}
      <button onClick={() => doc.refetch()}>Tải lại tài liệu</button>
      <SuggestionsTab document={doc.data} />
    </>
  );
}

function render(
  initial: { category: number; source: string; classified?: boolean; autoAfterFirstDocFetch?: boolean },
  jobStatus = "completed",
  scores = [0.87, 0.13],
) {
  const state = { classified: true, ...initial };
  const calls = mockFetch({
    "GET /api/auth/me": { body: { ...SESSION, features: ["classification"] } },
    "GET /api/documents/d1/category-suggestions": () => ({
      body: {
        document_id: "d1",
        job_id: "j1",
        job_status: state.classified ? jobStatus : null,
        items: (state.classified ? [1, 2] : []).map((id, i) => ({
          category_id: id,
          name: CATS[id],
          score: scores[i],
          is_current: id === state.category,
        })),
      },
    }),
    "POST /api/documents/d1/category-suggestions/accept": (call) => {
      state.category = (call.body as { category_id: number }).category_id;
      state.source = "user";
      return { body: { category_id: state.category, name: CATS[state.category], score: 0.13, is_current: true } };
    },
    "GET /api/documents/d1": () => {
      const body = {
        id: "d1",
        category: { id: state.category, name: CATS[state.category] },
        category_source: state.source,
        can_edit: true,
      };
      // worker tự phân loại ngay sau lần tải tài liệu đầu: trang đang giữ bản "chờ phân loại" cũ
      if (state.autoAfterFirstDocFetch)
        Object.assign(state, { category: 1, source: "auto", autoAfterFirstDocFetch: false });
      return { body };
    },
  });
  renderWithProviders(<Host />);
  return Object.assign(calls, { state });
}

const summary = () => screen.getByRole("region", { name: "Danh mục đang áp dụng" });
const row = (name: string) => screen.getByText(name, { selector: "li strong" }).closest("li") as HTMLElement;

describe("SuggestionsTab (P2-05, D-10)", () => {
  it("hiện danh mục đang áp dụng, nguồn tự động; chỉ dòng đó Đang áp dụng", async () => {
    render({ category: 1, source: "auto" });
    expect(await screen.findByText("Tự động phân loại")).toBeInTheDocument();
    expect(within(summary()).getByText("Hợp đồng")).toBeInTheDocument();
    expect(within(summary()).getByText("Độ tin cậy 87%")).toBeInTheDocument();
    expect(within(row("Hợp đồng")).getByText("Đang áp dụng")).toBeInTheDocument();
    expect(within(row("Công văn")).getByRole("button", { name: "Áp dụng" })).toBeInTheDocument();
  });

  it("bấm Áp dụng: khối đang áp dụng và danh sách cùng đổi, chỉ một danh mục đang áp dụng", async () => {
    const user = userEvent.setup();
    const calls = render({ category: 1, source: "auto" });
    await screen.findByText("Tự động phân loại");
    await user.click(within(row("Công văn")).getByRole("button", { name: "Áp dụng" }));

    expect(await within(summary()).findByText("Công văn")).toBeInTheDocument();
    expect(within(summary()).getByText("Người dùng chọn")).toBeInTheDocument();
    expect(screen.getAllByText("Đang áp dụng")).toHaveLength(1);
    expect(within(row("Công văn")).getByText("Đang áp dụng")).toBeInTheDocument();
    expect(within(row("Hợp đồng")).getByRole("button", { name: "Áp dụng" })).toBeInTheDocument();
    const post = calls.find((c) => c.method === "POST");
    expect(post?.body).toEqual({ category_id: 2 });
  });

  it("chờ phân loại sau khi job xong: báo người dùng tự chọn", async () => {
    render({ category: 9, source: "pending" });
    expect(await screen.findByText("Chờ phân loại")).toBeInTheDocument();
    expect(within(summary()).getByText("Chưa phân loại")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("chưa đủ chắc chắn");
    expect(screen.queryByText("Đang áp dụng")).not.toBeInTheDocument();
  });

  it("tài liệu được tải lại sau khi đã tự phân loại: danh sách gợi ý cũng tải lại", async () => {
    const user = userEvent.setup();
    const { state } = render({ category: 9, source: "pending", classified: false });
    expect(await screen.findByText("Đang chờ OCR xong để phân loại…")).toBeInTheDocument();
    Object.assign(state, { category: 1, source: "auto", classified: true }); // worker vừa OCR + phân loại xong
    await user.click(screen.getByRole("button", { name: "Tải lại tài liệu" }));
    expect(await within(summary()).findByText("Tự động phân loại")).toBeInTheDocument();
    expect(await screen.findByText("Đang áp dụng", {}, { timeout: 2000 })).toBeInTheDocument();
    expect(within(row("Hợp đồng")).getByText("Đang áp dụng")).toBeInTheDocument();
  });

  it("job đã hoàn tất ngay lần hỏi đầu mà tài liệu còn chờ: tải lại tài liệu", async () => {
    render({ category: 9, source: "pending", autoAfterFirstDocFetch: true });
    expect(await screen.findByText("Tự động phân loại", {}, { timeout: 2000 })).toBeInTheDocument();
    expect(within(summary()).getByText("Hợp đồng")).toBeInTheDocument();
    expect(within(row("Hợp đồng")).getByText("Đang áp dụng")).toBeInTheDocument();
  });
});
