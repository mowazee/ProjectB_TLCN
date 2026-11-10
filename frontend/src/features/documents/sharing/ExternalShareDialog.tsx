import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, Send } from "lucide-react";
import { useState, type FormEvent } from "react";

import { api } from "@/shared/api/client";
import type { DocumentOut, ExternalLinkCreated, ExternalLinks } from "@/shared/api/types";
import { Badge, ErrorBox, Field, Loading, Modal, fieldErrors } from "@/shared/components/ui";
import { formatDateTime } from "@/shared/lib/format";

const STATUS: Record<string, [string, "ok" | "neutral" | "danger"]> = {
  active: ["Còn hiệu lực", "ok"],
  expired: ["Hết hạn", "neutral"],
  revoked: ["Đã thu hồi", "danger"],
};
const EMAIL: Record<string, string> = { pending: "Đang gửi", sent: "Đã gửi", failed: "Gửi lỗi" };

/** FR-18 (SDD v0.13, D-13): gửi link xem tài liệu cho người ngoài hệ thống qua email; người nhận nhập OTP. */
export function ExternalShareDialog({ doc, onClose }: { doc: DocumentOut; onClose: () => void }) {
  const client = useQueryClient();
  const key = ["external-shares", doc.id];
  const links = useQuery({
    queryKey: key,
    queryFn: () => api<ExternalLinks>(`/api/documents/${doc.id}/external-shares`),
  });
  const [form, setForm] = useState({ recipient_email: "", expires_in_hours: 24, allow_download: false });
  const [created, setCreated] = useState<string | null>(null);
  const create = useMutation({
    mutationFn: () => api<ExternalLinkCreated>(`/api/documents/${doc.id}/external-shares`, { json: form }),
    onSuccess: (r) => {
      setCreated(r.url);
      setForm({ ...form, recipient_email: "" });
      client.invalidateQueries({ queryKey: key });
    },
  });
  const revoke = useMutation({
    mutationFn: (id: string) => api(`/api/external-shares/${id}`, { method: "DELETE" }),
    onSuccess: () => client.invalidateQueries({ queryKey: key }),
  });
  const errors = fieldErrors(create.error);
  const max = links.data?.max_hours ?? 24;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate();
  };

  return (
    <Modal title={`Chia sẻ ra ngoài: ${doc.title}`} onClose={onClose} size="lg">
      {links.isPending ? (
        <Loading />
      ) : links.data && !links.data.enabled ? (
        <ErrorBox error={new Error("Hệ thống chưa cấu hình gửi email (SMTP) nên chưa chia sẻ ra ngoài được.")} />
      ) : (
        <div className="stack">
          <p className="muted">
            Người nhận không cần tài khoản: họ mở link trong email, nhập mã xác thực gửi tới đúng email đó rồi xem tài
            liệu. Link tự hết hạn và mất hiệu lực khi tài liệu bị hủy xuất bản.
          </p>
          <form className="stack" onSubmit={submit}>
            <ErrorBox error={create.error} />
            <Field label="Email người nhận" htmlFor="xs-email" error={errors.recipient_email}>
              <input
                id="xs-email"
                className="input"
                type="email"
                required
                value={form.recipient_email}
                onChange={(e) => setForm({ ...form, recipient_email: e.target.value })}
              />
            </Field>
            <div className="row">
              <Field label={`Thời hạn (giờ, tối đa ${max})`} htmlFor="xs-hours" error={errors.expires_in_hours}>
                <input
                  id="xs-hours"
                  className="input"
                  type="number"
                  min={1}
                  max={max}
                  required
                  value={form.expires_in_hours}
                  onChange={(e) => setForm({ ...form, expires_in_hours: Number(e.target.value) })}
                />
              </Field>
              <label className="row" style={{ gap: 6 }}>
                <input
                  type="checkbox"
                  checked={form.allow_download}
                  onChange={(e) => setForm({ ...form, allow_download: e.target.checked })}
                />
                Cho phép tải file gốc và tài liệu đi kèm
              </label>
            </div>
            <div>
              <button className="btn btn-primary" type="submit" disabled={create.isPending}>
                <Send size={16} aria-hidden /> {create.isPending ? "Đang gửi..." : "Gửi link qua email"}
              </button>
            </div>
          </form>
          {created && (
            <div className="card stack" role="status">
              <strong>Đã tạo link và gửi email.</strong>
              <span className="muted">Link chỉ hiện một lần. Người nhận vẫn cần mã xác thực gửi tới email của họ.</span>
              <div className="row">
                <code className="grow" style={{ wordBreak: "break-all" }}>
                  {created}
                </code>
                <button className="btn btn-sm" onClick={() => void navigator.clipboard?.writeText(created)}>
                  <Copy size={14} aria-hidden /> Sao chép
                </button>
              </div>
            </div>
          )}
          <ErrorBox error={links.error ?? revoke.error} />
          {links.data && links.data.items.length > 0 && (
            <table className="table">
              <thead>
                <tr>
                  <th>Người nhận</th>
                  <th>Trạng thái</th>
                  <th>Hết hạn</th>
                  <th>Email</th>
                  <th>Lượt mở</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {links.data.items.map((l) => {
                  const [label, tone] = STATUS[l.status] ?? [l.status, "neutral"];
                  return (
                    <tr key={l.id}>
                      <td>
                        {l.recipient_email}
                        {l.allow_download && <span className="muted"> · được tải</span>}
                      </td>
                      <td>
                        <Badge tone={tone}>{label}</Badge>
                      </td>
                      <td>{formatDateTime(l.expires_at)}</td>
                      <td>{EMAIL[l.email_status] ?? l.email_status}</td>
                      <td>{l.access_count}</td>
                      <td>
                        {l.status === "active" && (
                          <button
                            className="btn btn-sm"
                            disabled={revoke.isPending}
                            onClick={() =>
                              window.confirm(`Thu hồi link gửi ${l.recipient_email}?`) && revoke.mutate(l.id)
                            }
                          >
                            Thu hồi
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      )}
    </Modal>
  );
}
