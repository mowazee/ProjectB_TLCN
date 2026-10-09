import { useQuery } from "@tanstack/react-query";

import { api } from "@/shared/api/client";
import type { Category } from "@/shared/api/types";

/** Danh mục (FR-02): activeOnly cho form upload/sửa - danh mục ngừng dùng không chọn được. */
export function useCategories(activeOnly = false) {
  return useQuery({
    queryKey: ["categories", { activeOnly }],
    queryFn: () => api<Category[]>("/api/categories", { query: { active_only: activeOnly } }),
    staleTime: 60_000,
  });
}
