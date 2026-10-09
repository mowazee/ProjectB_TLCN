import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/shared/api/client";
import type { CorrectionIn, CorrectionOut, PageDetail } from "@/shared/api/types";

export const pageKey = (docId: string, page: number) => ["page", docId, page] as const;

export function fetchPage(docId: string, page: number): Promise<PageDetail> {
  return api<PageDetail>(`/api/documents/${docId}/pages/${page}`);
}

export function usePageDetail(docId: string, page: number) {
  return useQuery({ queryKey: pageKey(docId, page), queryFn: () => fetchPage(docId, page) });
}

export function useSaveCorrection(docId: string, page: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: CorrectionIn) =>
      api<CorrectionOut>(`/api/documents/${docId}/pages/${page}/correction`, { method: "PUT", json: body }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: pageKey(docId, page) });
      client.invalidateQueries({ queryKey: ["versions", docId, page] });
      client.invalidateQueries({ queryKey: ["documents"] });
    },
  });
}
