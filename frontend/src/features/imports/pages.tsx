import { ClipboardList, Download, FolderUp } from "lucide-react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router";

import { POLL_MS } from "@/features/jobs";
import { api } from "@/shared/api/client";
import type { Category, ImportAccepted, ImportReport } from "@/shared/api/types";
import { CategoryModePicker, type CategoryMode } from "@/shared/components/CategoryModePicker";
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
import { useSession } from "@/shared/session";

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

const AUTO_HINT =
  "Mỗi file vào “Chưa phân loại”, hệ thống tự chọn danh mục sau khi OCR xong. Kết quả từng file xem ở báo cáo lô.";

/** metadata.csv mẫu: UTF-8 có BOM để Excel mở đúng tiếng Việt; mã danh mục lấy từ danh sách thật. */
function downloadTemplate(categories: Category[]) {
  const code = categories[0]?.code ?? "HOP-DONG";
  const rows = [
    "file_name,title,category,document_code",
    `hop-dong-45.pdf,Hợp đồng mua bán số 45/2026,${code},45/2026/HĐMB`,
    "cong-van-12.pdf,Công văn số 12 về số hóa hồ sơ,,12/CV-HCTH",
    "scan-001.pdf,,,",
  ];
  const url = URL.createObjectURL(new Blob(["\uFEFF" + rows.join("\r\n") + "\r\n"], { type: "text/csv" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = "metadata.csv";
  a.click();
  URL.revokeObjectURL(url);
}

/** UC-23 (P2-08): tải nhiều file hoặc ZIP + cách gán danh mục (+ metadata.csv) -> job BULK_IMPORT. */
export function ImportPage() {
  const categories = useCategories(true, { selectable: true });
  const { hasFeature } = useSession();
  const canAuto = hasFeature("classification"); // Danh mục gợi ý cần P2-05
  const [mode, setMode] = useState<CategoryMode>("auto");
  const categoryMode: CategoryMode = canAuto ? mode : "user";
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
    form.set("category_mode", categoryMode);
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
        {canAuto && (
          <Field label="Danh mục" error={errors.category_mode}>
            <CategoryModePicker
              value={mode}
              onChange={setMode}
              hints={{ auto: AUTO_HINT, user: "Một danh mục cho cả lô." }}
            />
          </Field>
        )}
        {categoryMode === "user" && (
          <Field label={canAuto ? "Chọn danh mục" : "Danh mục"} htmlFor="cat" error={errors.category_id}>
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
        )}
        <Field
          label="metadata.csv (tùy chọn)"
          htmlFor="meta"
          hint={
            <>
              Thông tin riêng cho từng file, khỏi sửa tay sau khi nhập. Cột <code>file_name</code> (bắt buộc),{" "}
              <code>title</code> (tiêu đề; trống = tên file), <code>category</code> (mã danh mục, ưu tiên hơn lựa chọn ở
              trên), <code>document_code</code> (số hiệu). Có thể đặt sẵn trong file ZIP.{" "}
              <button
                type="button"
                className="btn btn-sm"
                onClick={() => downloadTemplate(categories.data ?? [])}
                style={{ marginLeft: 4 }}
              >
                <Download size={14} aria-hidden /> Tải file mẫu
              </button>
            </>
          }
        >
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
const PENDING_POLL_MS = 10_000; // chờ OCR + tự phân loại (D-10) sau khi lô đã nhập xong
const SOURCE: Record<string, [string, "ok" | "warn" | "info" | "neutral"]> = {
  user: ["Người dùng chọn", "neutral"],
  auto: ["Tự động", "info"],
  pending: ["Chờ phân loại", "warn"],
};
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
    refetchInterval: (q) => {
      const data = q.state.data;
      if (!data || !DONE.has(data.status)) return POLL_MS;
      return data.files.some((f) => f.category_source === "pending") ? PENDING_POLL_MS : false;
    },
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
            <th>Danh mục</th>
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
                  {f.category_source ? (
                    <span className="row" style={{ gap: 6 }}>
                      {f.category_name}
                      <Badge tone={SOURCE[f.category_source]?.[1] ?? "neutral"}>
                        {SOURCE[f.category_source]?.[0] ?? f.category_source}
                      </Badge>
                    </span>
                  ) : (
                    "—"
                  )}
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
