import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/shared/api/client";
import type { Guide, Paged } from "@/shared/api/types";

/** FR-21 (v0.16): tài liệu hướng dẫn sử dụng - mọi người xem, Admin tải lên/sửa/xóa. */
export const guideKeys = { all: ["guides"] as const };

export const guideFileUrl = (id: string) => `/api/guides/${id}/file`;

export function useGuides(q: string, page: number) {
  return useQuery({
    queryKey: [...guideKeys.all, q, page],
    queryFn: () => api<Paged<Guide>>("/api/guides", { query: { q: q || undefined, page, page_size: 20 } }),
    placeholderData: (prev) => prev,
  });
}

export function useUploadGuide() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (form: FormData) => api<Guide>("/api/guides", { form }),
    onSuccess: () => client.invalidateQueries({ queryKey: guideKeys.all }),
  });
}

export function useUpdateGuide(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { title: string; description: string | null }) =>
      api<Guide>(`/api/guides/${id}`, { method: "PATCH", json: body }),
    onSuccess: () => client.invalidateQueries({ queryKey: guideKeys.all }),
  });
}

export function useDeleteGuide() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api<void>(`/api/guides/${id}`, { method: "DELETE" }),
    onSuccess: () => client.invalidateQueries({ queryKey: guideKeys.all }),
  });
}
