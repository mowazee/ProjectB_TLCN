import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { useJob } from "@/features/jobs";
import { api } from "@/shared/api/client";
import type { Field as FieldT, Fields } from "@/shared/api/types";
import { Badge, ErrorBox, JobBadge, Loading } from "@/shared/components/ui";
import type { DocumentSlotProps } from "@/shared/types/feature";

function FieldRow({ docId, field, canEdit }: { docId: string; field: FieldT; canEdit: boolean }) {
  const client = useQueryClient();
  const [value, setValue] = useState(field.field_value ?? "");
  const save = useMutation({
    mutationFn: (verified: boolean) =>
      api<FieldT>(`/api/documents/${docId}/fields/${field.field_name}`, {
        method: "PUT",
        json: { field_value: value.trim() || null, is_verified: verified },
      }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["fields", docId] }),
  });
  const changed = value !== (field.field_value ?? "");
  return (
    <tr>
      <td>
        <strong>{field.label}</strong>
        <div className="muted">{field.field_name}</div>
      </td>
      <td>
        {canEdit ? (
          <input className="input" value={value} onChange={(e) => setValue(e.target.value)} aria-label={field.label} />
        ) : (
          (field.field_value ?? <span className="muted">—</span>)
        )}
        <ErrorBox error={save.error} />
      </td>
      <td>
        {field.is_verified ? <Badge tone="ok">Đã xác nhận</Badge> : <Badge tone="warn">Chưa xác nhận</Badge>}
        <div className="muted">{field.extracted_method === "manual" ? "nhập tay" : (field.extracted_method ?? "")}</div>
      </td>
      <td>
        {canEdit && (
          <div className="row">
            <button className="btn btn-sm btn-primary" onClick={() => save.mutate(true)} disabled={save.isPending}>
              {changed ? "Lưu & xác nhận" : "Xác nhận"}
            </button>
            {field.is_verified && !changed && (
              <button className="btn btn-sm" onClick={() => save.mutate(false)} disabled={save.isPending}>
                Bỏ xác nhận
              </button>
            )}
          </div>
        )}
      </td>
    </tr>
  );
}

/** P2-04 (UC-21): trường chưa xác nhận hiển thị rõ; sửa/xác nhận có audit; chạy lại -> job EXTRACT. */
export function FieldsTab({ document }: DocumentSlotProps) {
  const client = useQueryClient();
  const fields = useQuery({
    queryKey: ["fields", document.id],
    queryFn: () => api<Fields>(`/api/documents/${document.id}/fields`),
  });
  const [jobId, setJobId] = useState<string | null>(null);
  useJob(jobId, () => client.invalidateQueries({ queryKey: ["fields", document.id] }));
  const extract = useMutation({
    mutationFn: () => api<{ job_id: string }>(`/api/documents/${document.id}/fields/extract`, { method: "POST" }),
    onSuccess: (r) => setJobId(r.job_id),
  });

  if (fields.isPending) return <Loading />;
  if (fields.error || !fields.data) return <ErrorBox error={fields.error} />;
  return (
    <div className="stack">
      <div className="row">
        <span className="muted">Trích xuất tự động:</span>
        <JobBadge status={fields.data.job_status} />
        {document.can_edit && (
          <button className="btn btn-sm" onClick={() => extract.mutate()} disabled={extract.isPending}>
            Trích xuất lại
          </button>
        )}
      </div>
      <ErrorBox error={extract.error} />
      <table className="table">
        <thead>
          <tr>
            <th>Trường</th>
            <th>Giá trị</th>
            <th>Trạng thái</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {fields.data.items.map((f) => (
            <FieldRow
              key={`${f.field_name}-${f.field_value}-${f.is_verified}`}
              docId={document.id}
              field={f}
              canEdit={document.can_edit}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}
