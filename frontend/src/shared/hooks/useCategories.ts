import { useQuery } from "@tanstack/react-query";

import { api } from "@/shared/api/client";
import type { Category } from "@/shared/api/types";

const withoutSystem = (cs: Category[]) => cs.filter((c) => !c.is_system);

/** Danh mục (FR-02): activeOnly cho form upload/sửa - danh mục ngừng dùng không chọn được.
 *  selectable (D-10): bỏ danh mục hệ thống "Chưa phân loại" - chỉ hệ thống gán, người dùng không tự chọn. */
export function useCategories(activeOnly = false, { selectable = false }: { selectable?: boolean } = {}) {
  return useQuery({
    queryKey: ["categories", { activeOnly }],
    queryFn: () => api<Category[]>("/api/categories", { query: { active_only: activeOnly } }),
    select: selectable ? withoutSystem : undefined,
    staleTime: 60_000,
  });
}
