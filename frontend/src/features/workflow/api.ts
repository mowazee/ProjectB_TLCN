import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/shared/api/client";
import type { ApprovalEntry, ApprovalState, Paged, ReviewItem, StorageLocation } from "@/shared/api/types";

export function useApprovalState(docId: string) {
  return useQuery({
    queryKey: ["approval", docId],
    queryFn: () => api<ApprovalState>(`/api/documents/${docId}/approval`),
  });
}

export function useApprovalHistory(docId: string) {
  return useQuery({
    queryKey: ["approval", docId, "history"],
    queryFn: () => api<ApprovalEntry[]>(`/api/documents/${docId}/approvals`),
  });
}

export interface ApprovalActionInput {
  action: string;
  comments?: string;
  /** D-12 (submit khi bật borrowing): có bản cứng không, kho/kệ khi có */
  has_physical_copy?: boolean;
  storage_location_id?: number;
  /** FR-19: submit (bắt buộc), approve (khi Kiểm duyệt viên sửa) */
  validity_status?: string;
  valid_until?: string | null;
}

export function usePhysicalCopyChoices(docId: string, enabled: boolean) {
  const locations = useQuery({
    queryKey: ["locations"],
    queryFn: () => api<StorageLocation[]>("/api/storage-locations"),
    enabled,
  });
  const current = useQuery({
    queryKey: ["doc-location", docId],
    queryFn: () =>
      api<{ storage_location: StorageLocation | null; has_physical_copy?: boolean | null }>(
        `/api/documents/${docId}/storage-location`,
      ),
    enabled,
  });
  return { locations, current };
}

export function useApprovalAction(docId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ action, comments, ...extra }: ApprovalActionInput) =>
      api<ApprovalState>(`/api/documents/${docId}/approval/${action}`, {
        method: "POST",
        json: { comments, ...extra },
      }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["approval", docId] });
      client.invalidateQueries({ queryKey: ["documents"] });
      client.invalidateQueries({ queryKey: ["reviews"] });
      client.invalidateQueries({ queryKey: ["doc-location", docId] });
    },
  });
}

export function useReviews(page: number) {
  return useQuery({
    queryKey: ["reviews", page],
    queryFn: () => api<Paged<ReviewItem>>("/api/reviews", { query: { page, page_size: 20 } }),
  });
}
