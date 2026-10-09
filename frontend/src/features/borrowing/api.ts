import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type Query } from "@/shared/api/client";
import type { Borrow, BorrowIn, Paged, StorageLocation } from "@/shared/api/types";

export function useBorrows(query: Query & { page: number }) {
  return useQuery({
    queryKey: ["borrows", query],
    queryFn: () => api<Paged<Borrow>>("/api/borrow-requests", { query: { ...query, page_size: 20 } }),
    placeholderData: (prev) => prev,
  });
}

export function useBorrowMutations() {
  const client = useQueryClient();
  const done = () => {
    client.invalidateQueries({ queryKey: ["borrows"] });
    client.invalidateQueries({ queryKey: ["notifications"] });
  };
  return {
    create: useMutation({
      mutationFn: (b: BorrowIn) => api<Borrow>("/api/borrow-requests", { json: b }),
      onSuccess: done,
    }),
    act: useMutation({
      mutationFn: ({ id, action }: { id: string; action: "approve" | "reject" | "return" }) =>
        api<Borrow>(`/api/borrow-requests/${id}/${action}`, { method: "POST" }),
      onSuccess: done,
    }),
  };
}

export function useLocations() {
  return useQuery({ queryKey: ["locations"], queryFn: () => api<StorageLocation[]>("/api/storage-locations") });
}

export function useSaveLocation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, name, code }: { id?: number; name: string; code: string }) =>
      id
        ? api<StorageLocation>(`/api/storage-locations/${id}`, { method: "PATCH", json: { name, code } })
        : api<StorageLocation>("/api/storage-locations", { json: { name, code } }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["locations"] }),
  });
}

export function useDocLocation(docId: string) {
  return useQuery({
    queryKey: ["doc-location", docId],
    queryFn: () => api<{ storage_location: StorageLocation | null }>(`/api/documents/${docId}/storage-location`),
  });
}

export function useSetDocLocation(docId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (locationId: number | null) =>
      api(`/api/documents/${docId}/storage-location`, { method: "PUT", json: { storage_location_id: locationId } }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["doc-location", docId] }),
  });
}
