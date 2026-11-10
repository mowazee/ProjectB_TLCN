import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Settings } from "lucide-react";
import { useState, type FormEvent } from "react";

import { api } from "@/shared/api/client";
import type { SystemSettings } from "@/shared/api/types";
import { ErrorBox, Field, Loading, PageHeader } from "@/shared/components/ui";

/** FR-14 (SDD v0.13): Admin cấu hình thời gian lưu thùng rác và audit log (audit tối thiểu 180 ngày). */
export function SettingsPage() {
  const client = useQueryClient();
  const current = useQuery({ queryKey: ["admin-settings"], queryFn: () => api<SystemSettings>("/api/admin/settings") });
  const save = useMutation({
    mutationFn: (data: SystemSettings) => api<SystemSettings>("/api/admin/settings", { method: "PUT", json: data }),
    onSuccess: (data) => client.setQueryData(["admin-settings"], data),
  });
  const [form, setForm] = useState<{ trash: string; audit: string } | null>(null);

  if (current.isPending) return <Loading />;
  const values = form ?? {
    trash: String(current.data?.trash_retention_days ?? ""),
    audit: String(current.data?.audit_retention_days ?? ""),
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    save.mutate(
      { trash_retention_days: Number(values.trash), audit_retention_days: Number(values.audit) },
      { onSuccess: () => setForm(null) },
    );
  };

  return (
    <div>
      <PageHeader
        icon={Settings}
        title="Cấu hình hệ thống"
        subtitle="Thời gian lưu trữ dữ liệu để tránh quá tải cơ sở dữ liệu. Giá trị mới áp dụng từ lượt dọn kế tiếp."
      />
      <ErrorBox error={current.error} />
      <form className="card stack" style={{ maxWidth: 520 }} onSubmit={submit}>
        <ErrorBox error={save.error} />
        <Field
          label="Giữ tài liệu trong thùng rác (ngày)"
          htmlFor="trash"
          hint="1–365 ngày. Quá hạn, hệ thống xóa cứng tài liệu và không khôi phục được."
        >
          <input
            id="trash"
            className="input"
            type="number"
            min={1}
            max={365}
            required
            value={values.trash}
            onChange={(e) => setForm({ ...values, trash: e.target.value })}
          />
        </Field>
        <Field
          label="Lưu audit log (ngày)"
          htmlFor="audit"
          hint="Tối thiểu 180, tối đa 3650 ngày. Chỉ xóa log vận hành (đăng nhập, quản trị, lượt xem/tải); lịch sử thay đổi của tài liệu được lưu vĩnh viễn. Số liệu thống kê không bị mất."
        >
          <input
            id="audit"
            className="input"
            type="number"
            min={180}
            max={3650}
            required
            value={values.audit}
            onChange={(e) => setForm({ ...values, audit: e.target.value })}
          />
        </Field>
        <div className="row">
          <button className="btn btn-primary" type="submit" disabled={save.isPending || form === null}>
            Lưu cấu hình
          </button>
          {save.isSuccess && form === null && <span className="muted">Đã lưu.</span>}
        </div>
      </form>
    </div>
  );
}
