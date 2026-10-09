import { useQuery } from "@tanstack/react-query";
import { ArcElement, BarElement, CategoryScale, Chart as ChartJS, Legend, LinearScale, Tooltip } from "chart.js";
import { Bar, Doughnut } from "react-chartjs-2";
import { Link } from "react-router";

import { api } from "@/shared/api/client";
import type { Dashboard } from "@/shared/api/types";
import { ErrorBox, Loading, PageHeader } from "@/shared/components/ui";
import { JOB_STATUS_LABELS, formatConfidence } from "@/shared/lib/format";
import { useSlots } from "@/shared/slots";

import s from "./dashboard.module.css";

ChartJS.register(ArcElement, BarElement, CategoryScale, LinearScale, Tooltip, Legend);

const JOB_COLORS: Record<string, string> = {
  queued: "#93c5fd",
  processing: "#3b82f6",
  completed: "#10b981",
  failed: "#ef4444",
};

function Stat({ label, value, to, hint }: { label: string; value: number | string; to?: string; hint?: string }) {
  const body = (
    <>
      <div className={s.value}>{value}</div>
      <div className={s.label} title={hint}>
        {label}
      </div>
    </>
  );
  return to ? (
    <Link to={to} className={`card ${s.stat}`}>
      {body}
    </Link>
  ) : (
    <div className={`card ${s.stat}`}>{body}</div>
  );
}

/** UC-07 (FR-08): số liệu theo phạm vi quyền; dữ liệu rỗng hiển thị 0; confidence KHÔNG gọi là accuracy. */
export function DashboardPage() {
  const { dashboardCards } = useSlots();
  const stats = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api<Dashboard>("/api/dashboard"),
    refetchInterval: 30_000,
  });
  if (stats.isPending) return <Loading />;
  if (stats.error || !stats.data) return <ErrorBox error={stats.error} />;
  const d = stats.data;
  const jobs = d.by_job_status;

  return (
    <div className="stack">
      <PageHeader title="Tổng quan" subtitle="Số liệu trong phạm vi tài liệu bạn được xem" />
      <div className={s.grid}>
        <Stat label="Tài liệu" value={d.documents} to="/documents" />
        <Stat label="Trang" value={d.pages} />
        <Stat label="Trang đã OCR" value={d.pages_ocr_done} />
        <Stat label="Trang cần xem lại" value={d.pages_needs_review} to="/documents?status=needs_review" />
        <Stat label="Job hoàn tất" value={d.jobs_completed} />
        <Stat label="Job lỗi" value={d.jobs_failed} to="/documents?status=failed" />
        <Stat label="Job đang chạy" value={d.jobs_in_progress} />
        <Stat
          label="Điểm tin cậy TB (confidence)"
          value={formatConfidence(d.avg_confidence)}
          hint="Điểm model tự đánh giá (0-100), không phải độ chính xác thực nghiệm"
        />
        {dashboardCards
          .filter((c) => c.key in d.extras)
          .map((c) => (
            <Stat key={c.key} label={c.label} value={d.extras[c.key] ?? 0} to={c.to} />
          ))}
      </div>
      <div className={s.charts}>
        <div className="card">
          <h2>Tài liệu theo danh mục</h2>
          {d.by_category.length ? (
            <Bar
              data={{
                labels: d.by_category.map((x) => x.label),
                datasets: [{ label: "Tài liệu", data: d.by_category.map((x) => x.count), backgroundColor: "#3b82f6" }],
              }}
              options={{
                plugins: { legend: { display: false } },
                scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
              }}
            />
          ) : (
            <p className="muted">Chưa có dữ liệu (0 tài liệu).</p>
          )}
        </div>
        <div className="card">
          <h2>Trạng thái OCR mới nhất</h2>
          {jobs.some((x) => x.count > 0) ? (
            <Doughnut
              data={{
                labels: jobs.map((x) => JOB_STATUS_LABELS[x.label] ?? x.label),
                datasets: [
                  {
                    data: jobs.map((x) => x.count),
                    backgroundColor: jobs.map((x) => JOB_COLORS[x.label] ?? "#94a3b8"),
                  },
                ],
              }}
            />
          ) : (
            <p className="muted">Chưa có job nào (0).</p>
          )}
        </div>
      </div>
    </div>
  );
}
