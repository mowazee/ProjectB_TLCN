import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { DocumentOut } from "@/shared/api/types";
import { mockFetch, renderWithProviders, SESSION } from "@/test/utils";

import { ShareDialog } from "./ShareDialog";

const DOC = { id: "d1", title: "Hợp đồng 01" } as DocumentOut;
const SHARING = {
  document_id: "d1",
  share_mode: "internal",
  is_published: true,
  owner_department: { id: 1, name: "Phòng A" },
  departments: [],
  users: [{ id: "u9", username: "hai", full_name: "Lê Hải", department_name: "Phòng A" }],
};
const DEPARTMENTS = [
  { id: 1, code: "A", name: "Phòng A" },
  { id: 2, code: "KT", name: "Phòng Kế toán" },
];
const LOOKUP = [{ id: "u7", username: "ketoan", full_name: "Lê Văn Kế Toán", department_name: "Phòng Kế toán" }];

function setup() {
  const calls = mockFetch({
    "GET /api/auth/me": { body: SESSION },
    "GET /api/documents/d1/sharing": { body: SHARING },
    "GET /api/departments": { body: DEPARTMENTS },
    "GET /api/users/lookup": { body: LOOKUP },
    "PUT /api/documents/d1/sharing": ({ body }) => ({ body: { ...SHARING, ...(body as object) } }),
  });
  const onClose = vi.fn();
  renderWithProviders(<ShareDialog doc={DOC} onClose={onClose} />);
  return { calls, onClose, u: userEvent.setup() };
}

describe("Hộp thoại chia sẻ (FR-13)", () => {
  it("chọn phòng ban, thêm người bằng bàn phím rồi lưu đúng cấu hình", async () => {
    const { calls, onClose, u } = setup();
    expect(await screen.findByRole("radio", { name: /Nội bộ/ })).toHaveAttribute("aria-checked", "true");
    const save = screen.getByRole("button", { name: "Lưu thay đổi" });
    expect(save).toBeDisabled(); // chưa thay đổi gì
    // Phòng ban của tài liệu luôn có quyền: hiện dạng khóa, không bấm được
    expect(screen.queryByRole("checkbox", { name: "Phòng A" })).toBeNull();
    // Người cùng phòng đã có quyền qua phòng ban
    expect(screen.getByText("Đã có quyền qua phòng ban")).toBeInTheDocument();

    await u.click(await screen.findByRole("checkbox", { name: "Phòng Kế toán" }));
    expect(screen.getByRole("checkbox", { name: "Phòng Kế toán" })).toHaveAttribute("aria-checked", "true");
    const combo = screen.getByRole("combobox");
    await u.type(combo, "ke");
    expect(await screen.findByRole("option", { name: /Lê Văn Kế Toán/ })).toBeInTheDocument();
    await u.keyboard("{ArrowDown}{Enter}");
    expect(
      within(screen.getByRole("list", { name: "Người được chia sẻ" })).getByText("Lê Văn Kế Toán"),
    ).toBeInTheDocument();
    expect(screen.getByText(/Phòng A, 1 phòng ban khác, 2 người được thêm có quyền xem/)).toBeInTheDocument();

    await u.click(screen.getByRole("button", { name: "Gỡ Lê Hải" }));
    await u.click(save);
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(calls.find((c) => c.method === "PUT")?.body).toEqual({
      share_mode: "internal",
      department_ids: [2],
      user_ids: ["u7"],
    });
  });

  it("Riêng tư bỏ danh sách phòng ban; Toàn hệ thống không cần thêm người", async () => {
    const { calls, u } = setup();
    await u.click(await screen.findByRole("checkbox", { name: "Phòng Kế toán" })); // chọn rồi đổi chế độ: phải bị bỏ
    await u.click(screen.getByRole("radio", { name: /Toàn hệ thống/ }));
    expect(screen.queryByRole("combobox")).toBeNull();
    expect(screen.getByText(/Mọi người dùng trong hệ thống có quyền xem/)).toBeInTheDocument();

    await u.click(screen.getByRole("radio", { name: /Riêng tư/ }));
    expect(screen.queryByRole("checkbox", { name: "Phòng Kế toán" })).toBeNull();
    expect(screen.getByText(/Chỉ bạn, 1 người được thêm có quyền xem/)).toBeInTheDocument();
    await u.click(screen.getByRole("button", { name: "Lưu thay đổi" }));
    await waitFor(() => expect(calls.some((c) => c.method === "PUT")).toBe(true));
    expect(calls.find((c) => c.method === "PUT")?.body).toEqual({
      share_mode: "private",
      department_ids: [],
      user_ids: ["u9"],
    });
  });

  it("Esc đầu tiên chỉ đóng gợi ý, Esc thứ hai mới đóng hộp thoại", async () => {
    const { onClose, u } = setup();
    const combo = await screen.findByRole("combobox");
    await u.type(combo, "ke");
    await screen.findByRole("option", { name: /Lê Văn Kế Toán/ });
    await u.keyboard("{Escape}");
    expect(screen.queryByRole("listbox")).toBeNull();
    expect(onClose).not.toHaveBeenCalled();
    await u.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalled();
  });
});
