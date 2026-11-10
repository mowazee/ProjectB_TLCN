/** FR-19 (SDD v0.14): nhãn hiệu lực tài liệu. Server trả validity_status đã tính hết hạn theo ngày hệ thống. */

export const VALIDITY_LABELS: Record<string, string> = {
  unspecified: "Không quy định",
  effective: "Còn hiệu lực",
  effective_until: "Còn hiệu lực đến ngày",
  expired: "Hết hiệu lực",
};

export const VALIDITY_OPTIONS = [
  { value: "effective", label: "Còn hiệu lực" },
  { value: "effective_until", label: "Còn hiệu lực đến ngày…" },
  { value: "expired", label: "Hết hiệu lực" },
  { value: "unspecified", label: "Không quy định" },
] as const;

export const VALIDITY_TONE: Record<string, "ok" | "warn" | "danger" | "neutral"> = {
  effective: "ok",
  effective_until: "warn",
  expired: "danger",
  unspecified: "neutral",
};

/** yyyy-mm-dd -> dd/mm/yyyy (không đổi múi giờ: đây là ngày, không phải thời điểm). */
export function formatDay(iso?: string | null): string {
  if (!iso) return "";
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
}

export function formatValidity(status: string, validUntil?: string | null): string {
  if (status === "effective_until" && validUntil) return `Còn hiệu lực đến ${formatDay(validUntil)}`;
  if (status === "expired" && validUntil) return `Hết hiệu lực (sau ${formatDay(validUntil)})`;
  return VALIDITY_LABELS[status] ?? status;
}

/** Ngày hôm nay theo giờ máy người dùng (server vẫn kiểm theo APP_TIMEZONE). */
export function todayISO(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/** Đổi hiệu lực khi tài liệu đã duyệt/xuất bản phải có lý do (D-14). */
export function validityReasonRequired(approvalStatus: string, workflow: boolean): boolean {
  return workflow && ["approved", "published", "unpublished"].includes(approvalStatus);
}
