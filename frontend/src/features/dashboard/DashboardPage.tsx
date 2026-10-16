import { useQuery } from "@tanstack/react-query";
import { BarElement, CategoryScale, Chart as ChartJS, LinearScale, Tooltip } from "chart.js";
import {
  CircleCheck,
  CircleX,
  Clock3,
  FileStack,
  FileText,
  Gauge,
  LayoutDashboard,
  LoaderCircle,
  ScanText,
  TriangleAlert,
  type LucideIcon,
} from "lucide-react";
import { Bar } from "react-chartjs-2";
import { Link } from "react-router";

import { api } from "@/shared/api/client";
import type { Dashboard } from "@/shared/api/types";
import { EmptyState, ErrorBox, Loading, PageHeader } from "@/shared/components/ui";
import { JOB_STATUS_LABELS, formatConfidence } from "@/shared/lib/format";
import { useSlots } from "@/shared/slots";

import s from "./dashboard.module.css";

ChartJS.register(BarElement, CategoryScale, LinearScale, Tooltip);

/** Một chuỗi số liệu -> một màu (slot 1 của bảng màu biểu đồ); lưới/trục nhạt để dữ liệu nổi lên. */
const SERIES_1 = "#2a78d6";
const GRID = "#eef2f7";
const INK_MUTED = "#64748b";

/** Trạng thái job: màu trạng thái chuẩn, luôn kèm icon + nhãn (không dùng màu đơn thuần). */
const JOB_STATES: { key: string; icon: LucideIcon; color: string }[] = [
  { key: "completed", icon: CircleCheck, color: "#0ca30c" },
  { key: "processing", icon: LoaderCircle, color: "#2a78d6" },
  { key: "queued", icon: Clock3, color: "#94a3b8" },
  { key: "failed", icon: CircleX, color: "#d03b3b" },
];

type Tone = "blue" | "violet" | "teal" | "amber" | "red" | "slate";

function Stat({
  label,
  value,
  icon: Icon,
  tone,
  to,
  hint,
}: {
  label: string;
  value: number | string;
  icon: LucideIcon;
  tone: Tone;
  to?: string;
  hint?: string;
}) {
  const body = (
    <>
      <span className={`${s.icon} ${s[tone]}`}>
        <Icon size={20} aria-hidden />
      </span>
      <div>
        <div className={s.value}>{value}</div>
        <div className={s.label} title={hint}>
          {label}
        </div>
      </div>
    </>
  );
  return to ? (
    <Link to={to} className={`card ${s.stat} ${s.link}`}>
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
  const jobCount = (key: string) => d.by_job_status.find((x) => x.label === key)?.count ?? 0;
  const jobTotal = JOB_STATES.reduce((n, j) => n + jobCount(j.key), 0);
  const extras = dashboardCards.filter((c) => c.key in d.extras);

  return (
    <div className="stack">
      <PageHeader title="Tổng quan" subtitle="Số liệu trong phạm vi tài liệu bạn được xem" icon={LayoutDashboard} />

      <section>
        <h2 className={s.groupTitle}>Tài liệu và trang</h2>
        <div className={s.grid}>
          <Stat label="Tài liệu" value={d.documents} icon={FileText} tone="blue" to="/documents" />
          <Stat label="Trang" value={d.pages} icon={FileStack} tone="violet" />
          <Stat label="Trang đã OCR" value={d.pages_ocr_done} icon={ScanText} tone="teal" />
          <Stat
            label="Trang cần xem lại"
            value={d.pages_needs_review}
            icon={TriangleAlert}
            tone={d.pages_needs_review > 0 ? "amber" : "slate"}
            to="/documents?status=needs_review"
          />
        </div>
      </section>

      <section>
        <h2 className={s.groupTitle}>Xử lý OCR</h2>
        <div className={s.grid}>
          <Stat label="Job hoàn tất" value={d.jobs_completed} icon={CircleCheck} tone="teal" />
          <Stat
            label="Job lỗi"
            value={d.jobs_failed}
            icon={CircleX}
            tone={d.jobs_failed > 0 ? "red" : "slate"}
            to="/documents?status=failed"
          />
          <Stat label="Job đang chạy" value={d.jobs_in_progress} icon={LoaderCircle} tone="blue" />
          <Stat
            label="Điểm tin cậy TB (confidence)"
            value={formatConfidence(d.avg_confidence)}
            icon={Gauge}
            tone="slate"
            hint="Điểm model tự đánh giá (0-100), không phải độ chính xác thực nghiệm"
          />
        </div>
      </section>

      {extras.length > 0 && (
        <section>
          <h2 className={s.groupTitle}>Quy trình</h2>
          <div className={s.grid}>
            {extras.map((c) => (
              <Stat
                key={c.key}
                label={c.label}
                value={d.extras[c.key] ?? 0}
                icon={c.icon ?? FileText}
                tone="violet"
                to={c.to}
              />
            ))}
          </div>
        </section>
      )}

      <div className={s.charts}>
        <div className="card">
          <h2>Tài liệu theo danh mục</h2>
          {d.by_category.length ? (
            <div className={s.chartBox} style={{ height: Math.max(160, d.by_category.length * 44) }}>
              <Bar
                data={{
                  labels: d.by_category.map((x) => x.label),
                  datasets: [
                    {
                      label: "Tài liệu",
                      data: d.by_category.map((x) => x.count),
                      backgroundColor: SERIES_1,
                      hoverBackgroundColor: "#1c5cab",
                      borderRadius: 4,
                      borderSkipped: "start",
                      maxBarThickness: 22,
                    },
                  ],
                }}
                options={{
                  indexAxis: "y",
                  maintainAspectRatio: false,
                  plugins: {
                    legend: { display: false },
                    tooltip: {
                      backgroundColor: "#0f172a",
                      padding: 10,
                      cornerRadius: 8,
                      displayColors: false,
                      callbacks: { label: (c) => `${c.parsed.x} tài liệu` },
                    },
                  },
                  scales: {
                    x: {
                      beginAtZero: true,
                      ticks: { precision: 0, color: INK_MUTED },
                      grid: { color: GRID },
                      border: { display: false },
                    },
                    y: { ticks: { color: "#334155" }, grid: { display: false }, border: { display: false } },
                  },
                }}
              />
            </div>
          ) : (
            <EmptyState icon={FileText}>Chưa có dữ liệu (0 tài liệu).</EmptyState>
          )}
        </div>
        <div className="card">
          <h2>Trạng thái job OCR</h2>
          {jobTotal > 0 ? (
            <ul className={s.states}>
              {JOB_STATES.map(({ key, icon: Icon, color }) => {
                const n = jobCount(key);
                const pct = Math.round((n / jobTotal) * 100);
                return (
                  <li key={key}>
                    <Icon size={18} style={{ color }} aria-hidden />
                    <span className={s.stateLabel}>{JOB_STATUS_LABELS[key] ?? key}</span>
                    <span className={s.stateCount}>
                      {n} <small>({pct}%)</small>
                    </span>
                    <span className={s.track} aria-hidden>
                      <span style={{ width: `${pct}%`, background: color }} />
                    </span>
                  </li>
                );
              })}
            </ul>
          ) : (
            <EmptyState icon={ScanText}>Chưa có job nào (0).</EmptyState>
          )}
        </div>
      </div>
    </div>
  );
}
