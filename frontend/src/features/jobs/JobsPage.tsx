import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ListTodo, RotateCcw, TriangleAlert } from "lucide-react";
import { Link, useLocation, useSearchParams } from "react-router";

import { api } from "@/shared/api/client";
import type { JobListItem, Paged } from "@/shared/api/types";
import {
  Badge,
  EmptyState,
  ErrorBox,
  JobBadge,
  Loading,
  PageHeader,
  Pagination,
  ProgressBar,
} from "@/shared/components/ui";
import { JOB_STATUS_LABELS, formatDateTime } from "@/shared/lib/format";

import { useRetryJob } from "./useJob";
import s from "./jobs.module.css";

const REFRESH_MS = 5_000; // trang tổng quan: thưa hơn poll từng job (2 giây)
const KIND_LABELS: Record<string, string> = {
  OCR: "OCR",
  EXTRACT: "Trích xuất trường",
  CLASSIFY: "Gợi ý danh mục",
  BULK_IMPORT: "Nhập hàng loạt",
};

function kindLabel(job: JobListItem): string {
  const label = KIND_LABELS[job.kind] ?? job.kind;
  return job.queue_name === "ocr_hw" ? `${label} chữ viết tay` : label;
}

function Target({ job }: { job: JobListItem }) {
  const { pathname, search } = useLocation();
  if (job.document_id) {
    return (
      <Link
        to={`/documents/${job.document_id}`}
        state={{ from: pathname + search, fromLabel: "hàng đợi xử lý" }} // nút quay lại ở trang chi tiết
      >
        {job.document_title ?? "Tài liệu"}
      </Link>
    );
  }
  if (job.kind === "BULK_IMPORT") return <Link to={`/imports/${job.id}`}>Báo cáo lô nhập</Link>;
  return <span className="muted">—</span>;
}

/** UC-27 (FR-11): job nền trong phạm vi xem; chạy lại job lỗi; đánh dấu job chờ quá lâu. */
export function JobsPage() {
  const client = useQueryClient();
  const [params, setParams] = useSearchParams();
  const page = Number(params.get("page") ?? 1);
  const status = params.get("status") ?? "";
  const kind = params.get("kind") ?? "";
  const jobs = useQuery({
    queryKey: ["jobs", page, status, kind],
    queryFn: () =>
      api<Paged<JobListItem>>("/api/jobs", {
        query: { page, page_size: 20, status: status || undefined, kind: kind || undefined },
      }),
    placeholderData: (prev) => prev,
    // còn job đang chờ/chạy thì làm mới định kỳ
    refetchInterval: (q) =>
      q.state.data?.items.some((j) => j.status === "queued" || j.status === "processing") ? REFRESH_MS : false,
  });
  const retry = useRetryJob();
  const update = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== "page") next.delete("page");
    setParams(next, { replace: true });
  };
  const stale = jobs.data?.items.filter((j) => j.stale).length ?? 0;

  return (
    <div>
      <PageHeader
        icon={ListTodo}
        title="Hàng đợi xử lý"
        subtitle="Job OCR, trích xuất, phân loại, nhập hàng loạt của tài liệu trong phạm vi của bạn"
      />
      <div className="row" style={{ marginBottom: 12 }}>
        <select
          className="select"
          style={{ width: "auto" }}
          aria-label="Lọc theo trạng thái"
          value={status}
          onChange={(e) => update("status", e.target.value)}
        >
          <option value="">Mọi trạng thái</option>
          {Object.entries(JOB_STATUS_LABELS).map(([v, label]) => (
            <option key={v} value={v}>
              {label}
            </option>
          ))}
        </select>
        <select
          className="select"
          style={{ width: "auto" }}
          aria-label="Lọc theo loại job"
          value={kind}
          onChange={(e) => update("kind", e.target.value)}
        >
          <option value="">Mọi loại</option>
          {Object.entries(KIND_LABELS).map(([v, label]) => (
            <option key={v} value={v}>
              {label}
            </option>
          ))}
        </select>
      </div>
      {stale > 0 && (
        <div className={s.warn} role="status">
          <TriangleAlert size={18} aria-hidden />
          <div>
            <strong>{stale} job chờ quá lâu.</strong> Worker xử lý có thể chưa chạy hoặc đã dừng (job OCR chữ viết tay
            cần worker hàng đợi <code>ocr_hw</code>). Hệ thống tự gửi lại định kỳ; nếu kéo dài, báo quản trị viên kiểm
            tra worker.
          </div>
        </div>
      )}
      <ErrorBox error={jobs.error ?? retry.error} />
      {jobs.isPending ? (
        <Loading />
      ) : !jobs.data?.items.length ? (
        <EmptyState icon={ListTodo}>Không có job nào.</EmptyState>
      ) : (
        <>
          <table className="table">
            <thead>
              <tr>
                <th>Loại</th>
                <th>Tài liệu</th>
                <th>Trạng thái</th>
                <th>Lần thử</th>
                <th>Thời gian</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {jobs.data.items.map((j) => (
                <tr key={j.id}>
                  <td>{kindLabel(j)}</td>
                  <td>
                    <Target job={j} />
                  </td>
                  <td>
                    <div className="row">
                      <JobBadge status={j.status} />
                      {j.stale && <Badge tone="warn">Chờ quá lâu</Badge>}
                    </div>
                    {(j.status === "processing" || j.status === "queued") && (
                      <div className={s.progress}>
                        <ProgressBar value={j.progress} />
                      </div>
                    )}
                    {j.status === "failed" && j.error_message && (
                      <div className={s.error}>
                        {j.error_message} <span className="muted">({j.error_code})</span>
                      </div>
                    )}
                  </td>
                  <td>
                    {j.attempt}/{j.max_attempts}
                  </td>
                  <td>
                    <div>{formatDateTime(j.queued_at)}</div>
                    {j.finished_at && <div className="muted">xong {formatDateTime(j.finished_at)}</div>}
                  </td>
                  <td>
                    {j.status === "failed" && (
                      <button
                        className="btn btn-sm"
                        disabled={retry.isPending}
                        onClick={() =>
                          retry.mutate(j.id, { onSuccess: () => client.invalidateQueries({ queryKey: ["jobs"] }) })
                        }
                      >
                        <RotateCcw size={14} aria-hidden /> Chạy lại
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <Pagination
            page={jobs.data.page}
            pageSize={jobs.data.page_size}
            total={jobs.data.total}
            onChange={(p) => update("page", String(p))}
          />
        </>
      )}
    </div>
  );
}
