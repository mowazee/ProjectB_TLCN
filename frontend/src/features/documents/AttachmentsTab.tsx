import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Download, Paperclip, Trash2 } from "lucide-react";
import { useRef } from "react";

import { api } from "@/shared/api/client";
import type { Attachment, DocumentOut } from "@/shared/api/types";
import { EmptyState, ErrorBox, Loading } from "@/shared/components/ui";
import { formatBytes, formatDateTime } from "@/shared/lib/format";

import { ATTACHMENT_ACCEPT, attachmentKey as key, attachmentUrl, bundleUrl, useAttachments } from "./attachments";

/** FR-15 (SDD v0.13): tài liệu đi kèm - xem/tải theo phạm vi xem, thêm/xóa theo quyền SỬA (D-11). */
export function AttachmentsTab({ document: d }: { document: DocumentOut }) {
  const client = useQueryClient();
  const list = useAttachments(d.id);
  const input = useRef<HTMLInputElement>(null);
  const canEdit = d.can_edit;
  const add = useMutation({
    mutationFn: (files: File[]) => {
      const form = new FormData();
      files.forEach((f) => form.append("files", f));
      return api<Attachment[]>(`/api/documents/${d.id}/attachments`, { form });
    },
    onSuccess: () => client.invalidateQueries({ queryKey: key(d.id) }),
  });
  const remove = useMutation({
    mutationFn: (id: string) => api(`/api/documents/${d.id}/attachments/${id}`, { method: "DELETE" }),
    onSuccess: () => client.invalidateQueries({ queryKey: key(d.id) }),
  });

  if (list.isPending) return <Loading />;
  const items = list.data ?? [];
  return (
    <div className="stack">
      <p className="muted">
        Tài liệu đi kèm không được OCR và không tìm kiếm theo nội dung. Dùng “Tải cả bộ” để tải file gốc cùng mọi tài
        liệu đi kèm (.zip).
      </p>
      <div className="row">
        {canEdit && (
          <>
            <input
              ref={input}
              type="file"
              multiple
              hidden
              accept={ATTACHMENT_ACCEPT}
              aria-label="Chọn tài liệu đi kèm"
              onChange={(e) => {
                const files = Array.from(e.target.files ?? []);
                if (files.length) add.mutate(files);
                e.target.value = "";
              }}
            />
            <button className="btn btn-primary" onClick={() => input.current?.click()} disabled={add.isPending}>
              <Paperclip size={16} aria-hidden /> {add.isPending ? "Đang tải lên..." : "Thêm tài liệu đi kèm"}
            </button>
          </>
        )}
        <a className="btn" href={bundleUrl(d.id)} download>
          <Download size={16} aria-hidden /> Tải cả bộ (.zip)
        </a>
      </div>
      {!canEdit && d.edit_lock_reason && <p className="muted">{d.edit_lock_reason}</p>}
      <ErrorBox error={list.error ?? add.error ?? remove.error} />
      {items.length === 0 ? (
        <EmptyState icon={Paperclip}>Chưa có tài liệu đi kèm.</EmptyState>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Tên file</th>
              <th>Dung lượng</th>
              <th>Thêm lúc</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {items.map((a) => (
              <tr key={a.id}>
                <td>
                  <a href={attachmentUrl(d.id, a.id)} download>
                    {a.file_name}
                  </a>
                </td>
                <td>{formatBytes(a.bytes)}</td>
                <td>{formatDateTime(a.created_at)}</td>
                <td>
                  {canEdit && (
                    <button
                      className="btn btn-sm btn-icon"
                      aria-label={`Xóa ${a.file_name}`}
                      disabled={remove.isPending}
                      onClick={() => window.confirm(`Xóa tài liệu đi kèm "${a.file_name}"?`) && remove.mutate(a.id)}
                    >
                      <Trash2 size={14} aria-hidden />
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
