import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/shared/api/client";
import type { ApprovalEntry, ApprovalState, Paged, ReviewItem } from "@/shared/api/types";

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

export function useApprovalAction(docId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ action, comments }: { action: string; comments?: string }) =>
      api<ApprovalState>(`/api/documents/${docId}/approval/${action}`, { method: "POST", json: { comments } }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["approval", docId] });
      client.invalidateQueries({ queryKey: ["documents"] });
      client.invalidateQueries({ queryKey: ["reviews"] });
    },
  });
}

export function useReviews(page: number) {
  return useQuery({
    queryKey: ["reviews", page],
    queryFn: () => api<Paged<ReviewItem>>("/api/reviews", { query: { page, page_size: 20 } }),
  });
}
