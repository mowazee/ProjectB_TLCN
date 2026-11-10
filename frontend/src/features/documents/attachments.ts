import { useQuery } from "@tanstack/react-query";

import { api } from "@/shared/api/client";
import type { Attachment } from "@/shared/api/types";

/** FR-15 (SDD v0.13): loại file cho phép (khớp backend documents/domain/attachments.py). */
export const ATTACHMENT_ACCEPT = ".pdf,.png,.jpg,.jpeg,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.odt,.ods,.txt,.csv";
export const attachmentUrl = (docId: string, id: string) => `/api/documents/${docId}/attachments/${id}/file`;
export const bundleUrl = (docId: string) => `/api/documents/${docId}/bundle`;

export const attachmentKey = (docId: string) => ["attachments", docId];

export function useAttachments(docId: string) {
  return useQuery({
    queryKey: attachmentKey(docId),
    queryFn: () => api<Attachment[]>(`/api/documents/${docId}/attachments`),
  });
}
