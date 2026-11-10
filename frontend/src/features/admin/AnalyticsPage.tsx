import { useQuery } from "@tanstack/react-query";
import {
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
} from "chart.js";
import { BarChart3, Download } from "lucide-react";
import { useState } from "react";
import { Bar, Line } from "react-chartjs-2";

import { api } from "@/shared/api/client";
import type { Analytics } from "@/shared/api/types";
import { EmptyState, ErrorBox, Field, Loading, PageHeader } from "@/shared/components/ui";
import { cssVar, useTheme } from "@/shared/theme";

import { useDepartments, useUsers } from "./api";
import s from "./analytics.module.css";

ChartJS.register(BarElement, CategoryScale, Legend, LinearScale, LineElement, PointElement, Tooltip);

type Row = Record<string, unknown>;

/** Chỉ số hiển thị ở bảng (cột) và trên biểu đồ xu hướng. */
const COLUMNS: { key: string; label: string; hint?: string }[] = [
  { key: "uploads", label: "Tải lên" },
  { key: "pages_uploaded", label: "Trang" },
  { key: "ocr_edits", label: "Sửa OCR" },
  { key: "submits", label: "Gửi duyệt" },
  { key: "approvals", label: "Duyệt" },
  { key: "rejections", label: "Từ chối" },
  { key: "publishes", label: "Xuất bản" },
  { key: "borrow_requests", label: "Mượn" },
  { key: "downloads", label: "Tải file" },
  { key: "job_failure_rate", label: "Job lỗi (%)" },
  { key: "avg_lead_hours", label: "TB tải lên → xuất bản (giờ)", hint: "Theo người tải lên" },
];
const TREND = ["uploads", "ocr_edits", "approvals", "publishes"];
const COMPARE = ["uploads", "approvals", "publishes"];

const iso = (d: Date) => d.toISOString().slice(0, 10);
const num = (v: unknown) => (typeof v === "number" ? v : 0);
const show = (v: unknown) => (v === null || v === undefined ? "—" : String(v));

function useAnalytics(params: Record<string, string | undefined>) {
  return useQuery({
    queryKey: ["admin-analytics", params],
    queryFn: () => api<Analytics>("/api/admin/analytics", { query: params }),
  });
}

/** FR-17 (SDD v0.13): Admin giám sát hoạt động theo người dùng, phòng ban, thời gian. */
export function AnalyticsPage() {
  const { theme } = useTheme();
  const today = new Date();
  const [from, setFrom] = useState(iso(new Date(today.getTime() - 29 * 86_400_000)));
  const [to, setTo] = useState(iso(today));
  const [granularity, setGranularity] = useState("day");
  const [department, setDepartment] = useState("");
  const [user, setUser] = useState("");
  const [compareBy, setCompareBy] = useState<"user" | "department">("department");
  const departments = useDepartments();
  const users = useUsers(1, { q: "", role: "", department_id: department, is_active: "" });
  const params = {
    from,
    to,
    granularity,
    department_id: department || undefined,
    user_id: user || undefined,
  };
  const data = useAnalytics(params);
  const colors = [1, 2, 3, 4].map((i) => cssVar(`--chart-series-${i}`));
  const axis = { grid: { color: cssVar("--chart-grid") }, ticks: { color: cssVar("--chart-ink-muted") } };
  const legend = { labels: { color: cssVar("--chart-ink") } };

  const exportUrl = `/api/admin/analytics/export.csv?${new URLSearchParams(
    Object.entries(params).filter((e): e is [string, string] => Boolean(e[1])),
  ).toString()}`;

  const d = data.data;
  const compareRows: Row[] = d ? (compareBy === "user" ? d.by_user : d.by_department).slice(0, 15) : [];
  const nameOf = (r: Row) =>
    compareBy === "user" ? String(r.full_name ?? r.username ?? "—") : String(r.department_name ?? "Chưa có phòng ban");

  return (
    <div className="stack">
      <PageHeader
        icon={BarChart3}
        title="Thống kê hoạt động"
        subtitle="Giám sát hiệu quả hoạt động của tài khoản và phòng ban. Số liệu tổng hợp theo ngày từ nhật ký."
        actions={
          <a className="btn" href={exportUrl} download>
            <Download size={16} aria-hidden /> Xuất CSV
          </a>
        }
      />
      <div className={`card ${s.filters}`}>
        <Field label="Từ ngày" htmlFor="af">
          <input
            id="af"
            className="input"
            type="date"
            value={from}
            max={to}
            onChange={(e) => setFrom(e.target.value)}
          />
        </Field>
        <Field label="Đến ngày" htmlFor="at">
          <input id="at" className="input" type="date" value={to} min={from} onChange={(e) => setTo(e.target.value)} />
        </Field>
        <Field label="Gom theo" htmlFor="ag">
          <select id="ag" className="select" value={granularity} onChange={(e) => setGranularity(e.target.value)}>
            <option value="day">Ngày</option>
            <option value="week">Tuần</option>
            <option value="month">Tháng</option>
          </select>
        </Field>
        <Field label="Phòng ban" htmlFor="ad">
          <select
            id="ad"
            className="select"
            value={department}
            onChange={(e) => {
              setDepartment(e.target.value);
              setUser("");
            }}
          >
            <option value="">Tất cả</option>
            {departments.data?.map((x) => (
              <option key={x.id} value={x.id}>
                {x.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Người dùng" htmlFor="au">
          <select id="au" className="select" value={user} onChange={(e) => setUser(e.target.value)}>
            <option value="">Tất cả</option>
            {users.data?.items.map((x) => (
              <option key={x.id} value={x.id}>
                {x.full_name || x.username}
              </option>
            ))}
          </select>
        </Field>
      </div>
      <ErrorBox error={data.error} />
      {data.isPending ? (
        <Loading />
      ) : !d ? null : (
        <>
          <div className={s.kpis}>
            {[
              ["Tài liệu tải lên", d.totals.uploads],
              ["Trang tải lên", d.totals.pages_uploaded],
              ["Lần sửa OCR", d.totals.ocr_edits],
              ["Xuất bản", d.totals.publishes],
              ["Tỉ lệ job lỗi", d.totals.job_failure_rate === null ? "—" : `${String(d.totals.job_failure_rate)}%`],
              [
                "TB tải lên → xuất bản",
                d.totals.avg_lead_hours === null ? "—" : `${String(d.totals.avg_lead_hours)} giờ`,
              ],
            ].map(([label, value]) => (
              <div key={String(label)} className={`card ${s.kpi}`}>
                <span className="muted">{String(label)}</span>
                <strong>{show(value)}</strong>
              </div>
            ))}
          </div>

          <section className="card">
            <h2 className={s.title}>
              Xu hướng theo {granularity === "day" ? "ngày" : granularity === "week" ? "tuần" : "tháng"}
            </h2>
            <div className={s.chart}>
              <Line
                key={theme}
                aria-label="Biểu đồ xu hướng"
                data={{
                  labels: d.series.map((p) => String(p.period)),
                  datasets: TREND.map((k, i) => ({
                    label: COLUMNS.find((c) => c.key === k)?.label ?? k,
                    data: d.series.map((p) => num((p as Row)[k])),
                    borderColor: colors[i],
                    backgroundColor: colors[i],
                    tension: 0.25,
                    pointRadius: 2,
                  })),
                }}
                options={{
                  maintainAspectRatio: false,
                  interaction: { mode: "index", intersect: false },
                  plugins: { legend },
                  scales: { x: axis, y: { ...axis, beginAtZero: true, ticks: { ...axis.ticks, precision: 0 } } },
                }}
              />
            </div>
          </section>

          <section className="card">
            <div className="row">
              <h2 className={`${s.title} grow`}>So sánh</h2>
              <div className="row" role="group" aria-label="So sánh theo">
                <button
                  className={`btn btn-sm ${compareBy === "department" ? "btn-primary" : ""}`}
                  onClick={() => setCompareBy("department")}
                  aria-pressed={compareBy === "department"}
                >
                  Phòng ban
                </button>
                <button
                  className={`btn btn-sm ${compareBy === "user" ? "btn-primary" : ""}`}
                  onClick={() => setCompareBy("user")}
                  aria-pressed={compareBy === "user"}
                >
                  Người dùng
                </button>
              </div>
            </div>
            {compareRows.length ? (
              <div className={s.chart} style={{ height: Math.max(200, compareRows.length * 36) }}>
                <Bar
                  key={`${theme}-${compareBy}`}
                  aria-label="Biểu đồ so sánh"
                  data={{
                    labels: compareRows.map(nameOf),
                    datasets: COMPARE.map((k, i) => ({
                      label: COLUMNS.find((c) => c.key === k)?.label ?? k,
                      data: compareRows.map((r) => num(r[k])),
                      backgroundColor: colors[i],
                      borderRadius: 3,
                      maxBarThickness: 16,
                    })),
                  }}
                  options={{
                    indexAxis: "y",
                    maintainAspectRatio: false,
                    plugins: { legend },
                    scales: { x: { ...axis, beginAtZero: true, ticks: { ...axis.ticks, precision: 0 } }, y: axis },
                  }}
                />
              </div>
            ) : (
              <EmptyState>Không có hoạt động trong khoảng thời gian này.</EmptyState>
            )}
          </section>

          <section className="card">
            <h2 className={s.title}>Chi tiết theo {compareBy === "user" ? "người dùng" : "phòng ban"}</h2>
            <div className={s.tableWrap}>
              <table className="table">
                <thead>
                  <tr>
                    <th>{compareBy === "user" ? "Người dùng" : "Phòng ban"}</th>
                    {compareBy === "user" && <th>Phòng ban</th>}
                    {COLUMNS.map((c) => (
                      <th key={c.key} title={c.hint} className={s.num}>
                        {c.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(compareBy === "user" ? d.by_user : d.by_department).map((r: Row, i) => (
                    <tr key={String(r.user_id ?? r.department_id ?? i)}>
                      <td>{nameOf(r)}</td>
                      {compareBy === "user" && <td>{show(r.department_name)}</td>}
                      {COLUMNS.map((c) => (
                        <td key={c.key} className={s.num}>
                          {show(r[c.key])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
