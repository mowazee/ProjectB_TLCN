import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/shared/api/client";
import type {
  Department,
  DocumentOut,
  DocumentPatch,
  PageSummary,
  Paged,
  Sharing,
  SharingIn,
  UploadOut,
  UserLookup,
} from "@/shared/api/types";

export interface DocumentFilters {
  page: number;
  page_size: number;
  q?: string;
  category_id?: number;
  status?: string;
  approval_status?: string;
  lifecycle_status?: "active" | "deleted";
  /** FR-13: "with_me" = tài liệu người khác chia sẻ tới mình */
  shared?: "with_me";
}

export const documentKeys = {
  all: ["documents"] as const,
  list: (f: DocumentFilters) => ["documents", "list", f] as const,
  detail: (id: string) => ["documents", "detail", id] as const,
  pages: (id: string) => ["documents", "pages", id] as const,
  sharing: (id: string) => ["documents", "sharing", id] as const,
};

export function useDocuments(filters: DocumentFilters) {
  return useQuery({
    queryKey: documentKeys.list(filters),
    queryFn: () => api<Paged<DocumentOut>>("/api/documents", { query: { ...filters } }),
    placeholderData: (prev) => prev,
  });
}

export function useDocument(id: string) {
  return useQuery({ queryKey: documentKeys.detail(id), queryFn: () => api<DocumentOut>(`/api/documents/${id}`) });
}

export function usePages(id: string, enabled = true) {
  return useQuery({
    queryKey: documentKeys.pages(id),
    queryFn: () => api<PageSummary[]>(`/api/documents/${id}/pages`),
    enabled,
  });
}

export function useUpload() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (form: FormData) => api<UploadOut>("/api/documents", { form }),
    onSuccess: () => client.invalidateQueries({ queryKey: documentKeys.all }),
  });
}

export function useUpdateDocument(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (patch: DocumentPatch) => api<DocumentOut>(`/api/documents/${id}`, { method: "PATCH", json: patch }),
    onSuccess: (doc) => {
      client.setQueryData(documentKeys.detail(id), doc);
      client.invalidateQueries({ queryKey: documentKeys.all });
    },
  });
}

export function useDeleteDocument() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api<void>(`/api/documents/${id}`, { method: "DELETE" }),
    onSuccess: () => client.invalidateQueries({ queryKey: documentKeys.all }),
  });
}

export function useRestoreDocument() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api<DocumentOut>(`/api/documents/${id}/restore`, { method: "POST" }),
    onSuccess: () => client.invalidateQueries({ queryKey: documentKeys.all }),
  });
}

export const fileUrl = (id: string) => `/api/documents/${id}/file`;
export const pageImageUrl = (id: string, page: number) => `/api/documents/${id}/pages/${page}/image`;

// ---------------------------------------------------------------- FR-13 chia sẻ (v0.8)
export function useSharing(id: string, enabled: boolean) {
  return useQuery({
    queryKey: documentKeys.sharing(id),
    queryFn: () => api<Sharing>(`/api/documents/${id}/sharing`),
    enabled,
  });
}

export function useSaveSharing(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (data: SharingIn) => api<Sharing>(`/api/documents/${id}/sharing`, { method: "PUT", json: data }),
    onSuccess: (sharing) => {
      client.setQueryData(documentKeys.sharing(id), sharing);
      client.invalidateQueries({ queryKey: documentKeys.all }); // nhãn chế độ ở chi tiết và danh sách
    },
  });
}

/** Phòng ban để chọn chia sẻ (GET /api/departments mở cho mọi người dùng đã đăng nhập). */
export function useDepartmentOptions(enabled: boolean) {
  return useQuery({
    queryKey: ["departments"],
    queryFn: () => api<Department[]>("/api/departments"),
    staleTime: 60_000,
    enabled,
  });
}

/** Tra cứu người dùng để chia sẻ: chỉ gọi khi gõ đủ 2 ký tự (server cũng chặn). */
export function useUserLookup(q: string) {
  const term = q.trim();
  return useQuery({
    queryKey: ["users", "lookup", term],
    queryFn: () => api<UserLookup[]>("/api/users/lookup", { query: { q: term } }),
    enabled: term.length >= 2,
    staleTime: 30_000,
    placeholderData: (prev) => prev,
  });
}
