import { ChevronLeft, ChevronRight, CircleAlert, Inbox, X, type LucideIcon } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";

import { ApiError, errorMessage } from "@/shared/api/client";
import { APPROVAL_LABELS, JOB_STATUS_LABELS, PAGE_STATUS_LABELS } from "@/shared/lib/format";

import s from "./ui.module.css";

export function Spinner({ label = "Đang tải" }: { label?: string }) {
  return <span className={s.spinner} role="status" aria-label={label} />;
}

export function Loading() {
  return (
    <div className={s.center}>
      <Spinner />
    </div>
  );
}

export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null;
  const requestId = error instanceof ApiError ? error.requestId : null;
  return (
    <div className={s.error} role="alert">
      <CircleAlert size={18} className={s.errorIcon} aria-hidden />
      <div>
        {errorMessage(error)}
        {requestId && <small>Mã tra cứu: {requestId}</small>}
      </div>
    </div>
  );
}

export function EmptyState({ children, icon: Icon = Inbox }: { children: ReactNode; icon?: LucideIcon }) {
  return (
    <div className={s.empty}>
      <span className={s.emptyIcon}>
        <Icon size={24} aria-hidden />
      </span>
      <div>{children}</div>
    </div>
  );
}

export function PageHeader({
  title,
  subtitle,
  actions,
  icon: Icon,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  icon?: LucideIcon;
}) {
  return (
    <div className={s.header}>
      <div className={s.titleRow}>
        {Icon && (
          <span className={s.titleIcon}>
            <Icon size={22} aria-hidden />
          </span>
        )}
        <div>
          <h1>{title}</h1>
          {subtitle && <p className="muted">{subtitle}</p>}
        </div>
      </div>
      {actions && <div className="row">{actions}</div>}
    </div>
  );
}

type Tone = "ok" | "warn" | "danger" | "info" | "neutral";

export function Badge({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  return <span className={`${s.badge} ${tone !== "neutral" ? s[tone] : ""}`}>{children}</span>;
}

const JOB_TONE: Record<string, Tone> = { queued: "info", processing: "info", completed: "ok", failed: "danger" };
const PAGE_TONE: Record<string, Tone> = { completed: "ok", needs_review: "warn", failed: "danger" };
const APPROVAL_TONE: Record<string, Tone> = {
  pending_review: "info",
  approved: "ok",
  published: "ok",
  rejected: "danger",
  unpublished: "warn",
};

/** errorCode = "CANCELLED": job người dùng đã dừng (status failed) -> nhãn trung tính "Đã dừng" thay vì "Lỗi". */
export function JobBadge({ status, errorCode }: { status: string | null | undefined; errorCode?: string | null }) {
  if (!status) return <span className="muted">—</span>;
  if (status === "failed" && errorCode === "CANCELLED") return <Badge>Đã dừng</Badge>;
  return <Badge tone={JOB_TONE[status] ?? "neutral"}>{JOB_STATUS_LABELS[status] ?? status}</Badge>;
}

export function PageStatusBadge({ status }: { status: string }) {
  return <Badge tone={PAGE_TONE[status] ?? "neutral"}>{PAGE_STATUS_LABELS[status] ?? status}</Badge>;
}

export function ApprovalBadge({ status }: { status: string }) {
  return <Badge tone={APPROVAL_TONE[status] ?? "neutral"}>{APPROVAL_LABELS[status] ?? status}</Badge>;
}

export function ProgressBar({ value }: { value: number }) {
  return (
    <div className={s.progress} role="progressbar" aria-valuenow={value} aria-valuemin={0} aria-valuemax={100}>
      <div className={s.progressBar} style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
    </div>
  );
}

export function Pagination({
  page,
  pageSize,
  total,
  onChange,
}: {
  page: number;
  pageSize: number;
  total: number;
  onChange: (page: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className={s.pager}>
      <span className="muted">
        {total} kết quả · trang {page}/{pages}
      </span>
      <button className="btn btn-sm" disabled={page <= 1} onClick={() => onChange(page - 1)}>
        <ChevronLeft size={15} aria-hidden /> Trước
      </button>
      <button className="btn btn-sm" disabled={page >= pages} onClick={() => onChange(page + 1)}>
        Sau <ChevronRight size={15} aria-hidden />
      </button>
    </div>
  );
}

export function Field({
  label,
  hint,
  error,
  children,
  htmlFor,
}: {
  label: string;
  hint?: ReactNode;
  error?: string;
  children: ReactNode;
  htmlFor?: string;
}) {
  return (
    <div className={s.field}>
      <label htmlFor={htmlFor}>{label}</label>
      {children}
      {hint && <span className={s.hint}>{hint}</span>}
      {error && <span className={s.fieldError}>{error}</span>}
    </div>
  );
}

export function Modal({
  title,
  children,
  onClose,
  actions,
  aside,
  closeLabel = "Đóng",
  size = "md",
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  actions?: ReactNode;
  /** Nội dung bên trái thanh nút (vd. tóm tắt "ai có quyền"). */
  aside?: ReactNode;
  closeLabel?: string;
  size?: "md" | "lg";
}) {
  // Esc đóng hộp thoại (ngoài nút X và bấm ra ngoài)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className={s.backdrop} onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div
        className={`${s.modal} ${size === "lg" ? s.modalLg : ""}`}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <div className={s.modalHead}>
          <h2>{title}</h2>
          <button className="btn btn-ghost btn-sm btn-icon" onClick={onClose} aria-label="Đóng hộp thoại">
            <X size={18} aria-hidden />
          </button>
        </div>
        <div className={s.modalBody}>{children}</div>
        <div className={s.modalActions}>
          {aside && <div className={s.modalAside}>{aside}</div>}
          <button className="btn" onClick={onClose}>
            {closeLabel}
          </button>
          {actions}
        </div>
      </div>
    </div>
  );
}

export interface TabDef {
  id: string;
  label: string;
  render: () => ReactNode;
}

export function Tabs({ tabs, initial }: { tabs: TabDef[]; initial?: string }) {
  const [active, setActive] = useState(initial ?? tabs[0]?.id);
  const current = tabs.find((t) => t.id === active) ?? tabs[0];
  if (!current) return null;
  return (
    <div>
      <div className={s.tabs} role="tablist">
        {tabs.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={t.id === current.id}
            className={`${s.tab} ${t.id === current.id ? s.tabActive : ""}`}
            onClick={() => setActive(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div role="tabpanel">{current.render()}</div>
    </div>
  );
}

/** Lỗi theo trường từ envelope 422/409 ({fields}) để hiện dưới ô nhập. */
export function fieldErrors(err: unknown): Record<string, string> {
  return err instanceof ApiError && err.fields ? err.fields : {};
}
