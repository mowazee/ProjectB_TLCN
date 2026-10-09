import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/shared/api/client";
import type { DocumentOut, DocumentPatch, PageSummary, Paged, UploadOut } from "@/shared/api/types";

export interface DocumentFilters {
  page: number;
  page_size: number;
  q?: string;
  category_id?: number;
  status?: string;
  lifecycle_status?: "active" | "deleted";
}

export const documentKeys = {
  all: ["documents"] as const,
  list: (f: DocumentFilters) => ["documents", "list", f] as const,
  detail: (id: string) => ["documents", "detail", id] as const,
  pages: (id: string) => ["documents", "pages", id] as const,
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
