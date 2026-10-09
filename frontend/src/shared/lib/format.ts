/** Định dạng hiển thị (thời gian API là ISO 8601 UTC -> giờ địa phương). */

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("vi-VN", { dateStyle: "short", timeStyle: "short" });
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00` : iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("vi-VN");
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

export const JOB_STATUS_LABELS: Record<string, string> = {
  queued: "Đang chờ",
  processing: "Đang xử lý",
  completed: "Hoàn tất",
  failed: "Lỗi",
};

export const PAGE_STATUS_LABELS: Record<string, string> = {
  pending: "Chưa xử lý",
  completed: "Đã OCR",
  failed: "Lỗi",
  needs_review: "Cần xem lại",
};

export const APPROVAL_LABELS: Record<string, string> = {
  draft: "Nháp",
  pending_review: "Chờ duyệt",
  approved: "Đã duyệt",
  rejected: "Bị từ chối",
  published: "Đã xuất bản",
  unpublished: "Đã hủy xuất bản",
};

export const ROLE_LABELS: Record<string, string> = {
  ADMIN: "Quản trị viên",
  OFFICER: "Nghiệp vụ",
  APPROVER: "Kiểm duyệt",
};

/** Confidence là điểm model tự đánh giá, không phải độ chính xác (NFR-08). */
export function formatConfidence(v: number | string | null | undefined): string {
  if (v === null || v === undefined || v === "") return "—";
  return `${Number(v).toFixed(1)}`;
}
