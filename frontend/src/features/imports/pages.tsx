import { ClipboardList, FolderUp } from "lucide-react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router";

import { POLL_MS } from "@/features/jobs";
import { api } from "@/shared/api/client";
import type { ImportAccepted, ImportReport } from "@/shared/api/types";
import {
  Badge,
  ErrorBox,
  Field,
  JobBadge,
  Loading,
  PageHeader,
  ProgressBar,
  fieldErrors,
} from "@/shared/components/ui";
import { useCategories } from "@/shared/hooks/useCategories";
import { formatDateTime } from "@/shared/lib/format";

const RECENT_KEY = "imports.recent";

function recent(): string[] {
  try {
    return JSON.parse(localStorage.getItem(RECENT_KEY) ?? "[]") as string[];
  } catch {
    return [];
  }
}

function remember(jobId: string) {
  try {
    localStorage.setItem(RECENT_KEY, JSON.stringify([jobId, ...recent().filter((x) => x !== jobId)].slice(0, 10)));
  } catch {
    /* localStorage chỉ là tiện ích, có thể bị chặn */
  }
}

/** UC-23 (P2-08): tải nhiều file hoặc ZIP + danh mục (+ metadata.csv) -> job BULK_IMPORT. */
export function ImportPage() {
  const categories = useCategories(true, { selectable: true });
  const navigate = useNavigate();
  const [count, setCount] = useState(0);
  const start = useMutation({
    mutationFn: (form: FormData) => api<ImportAccepted>("/api/imports", { form }),
    onSuccess: (r) => {
      remember(r.job_id);
      navigate(`/imports/${r.job_id}`);
    },
  });
  const errors = fieldErrors(start.error);
  const submit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const meta = form.get("metadata");
    if (meta instanceof File && meta.size === 0) form.delete("metadata");
    start.mutate(form);
  };
  const history = recent();

  return (
    <div style={{ maxWidth: 720 }}>
      <PageHeader
        icon={FolderUp}
        title="Nhập hàng loạt"
        subtitle="Mỗi file được kiểm tra như khi tải lên từng file; file lỗi không làm hỏng cả lô."
      />
      <form className="card stack" onSubmit={submit}>
        <ErrorBox error={start.error} />
        <Field
          label="Các file (PDF/PNG/JPG) hoặc file ZIP"
          htmlFor="files"
          error={errors.files}
          hint={count ? `${count} file đã chọn` : undefined}
        >
          <input
            id="files"
            name="files"
            type="file"
            multiple
            accept=".pdf,.png,.jpg,.jpeg,.zip"
            required
            onChange={(e) => setCount(e.target.files?.length ?? 0)}
          />
        </Field>
        <Field label="Danh mục" htmlFor="cat" error={errors.category_id}>
          <select id="cat" name="category_id" className="select" required defaultValue="">
            <option value="" disabled>
              — Chọn danh mục —
            </option>
            {categories.data?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="metadata.csv (tùy chọn)" htmlFor="meta" hint="Cột file_name, title. Có thể đặt sẵn trong ZIP.">
          <input id="meta" name="metadata" type="file" accept=".csv,text/csv" />
        </Field>
        <div>
          <button className="btn btn-primary" type="submit" disabled={start.isPending}>
            {start.isPending ? "Đang tải lên..." : "Bắt đầu nhập"}
          </button>
        </div>
      </form>
      {history.length > 0 && (
        <div className="card" style={{ marginTop: 16 }}>
          <h3>Lô gần đây (trên trình duyệt này)</h3>
          <ul>
            {history.map((id) => (
              <li key={id}>
                <Link to={`/imports/${id}`}>{id}</Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

const DONE = new Set(["completed", "failed"]);
const FILE_STATUS: Record<string, [string, "ok" | "danger" | "info"]> = {
  imported: ["Đã nhập", "ok"],
  importing: ["Đã nhập", "ok"],
  error: ["Lỗi", "danger"],
};

export function ImportReportPage() {
  const { jobId = "" } = useParams();
  const report = useQuery({
    queryKey: ["import", jobId],
    queryFn: () => api<ImportReport>(`/api/imports/${jobId}`),
    refetchInterval: (q) => (q.state.data && DONE.has(q.state.data.status) ? false : POLL_MS),
  });
  if (report.isPending) return <Loading />;
  if (report.error || !report.data) return <ErrorBox error={report.error} />;
  const r = report.data;
  return (
    <div className="stack">
      <PageHeader
        icon={ClipboardList}
        title="Báo cáo nhập hàng loạt"
        subtitle={`Bắt đầu ${formatDateTime(r.queued_at)}${r.finished_at ? ` · xong ${formatDateTime(r.finished_at)}` : ""}`}
        actions={
          <Link className="btn" to="/imports">
            Nhập lô khác
          </Link>
        }
      />
      <div className="card stack">
        <div className="row">
          <JobBadge status={r.status} />
          <span>
            {r.imported}/{r.total} file đã nhập · {r.errors} lỗi
          </span>
          {r.error_code && <Badge tone="danger">{r.error_code}</Badge>}
        </div>
        {!DONE.has(r.status) && <ProgressBar value={r.progress} />}
      </div>
      <table className="table">
        <thead>
          <tr>
            <th>File</th>
            <th>Kết quả</th>
            <th>Chi tiết</th>
          </tr>
        </thead>
        <tbody>
          {r.files.map((f) => {
            const [label, tone] = FILE_STATUS[f.status ?? ""] ?? [f.status ?? "—", "info"];
            return (
              <tr key={f.name}>
                <td>{f.name}</td>
                <td>
                  <Badge tone={tone}>{label}</Badge>
                </td>
                <td>
                  {f.document_id ? (
                    <Link to={`/documents/${f.document_id}`}>Mở tài liệu</Link>
                  ) : (
                    <span>
                      {f.message} {f.code && <code>({f.code})</code>}
                    </span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
