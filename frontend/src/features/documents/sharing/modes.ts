import { Building2, Earth, Lock, type LucideIcon } from "lucide-react";

/** FR-13 / D-09: ba chế độ chia sẻ của tài liệu đã xuất bản (khớp ShareMode ở backend). */
export type ShareMode = "private" | "internal" | "public";

export interface ShareModeInfo {
  label: string;
  short: string;
  icon: LucideIcon;
  /** Tông màu badge/icon (cặp --tone-*-bg/fg) */
  tone: "slate" | "blue" | "teal";
}

export const SHARE_MODES: Record<ShareMode, ShareModeInfo> = {
  private: { label: "Riêng tư", short: "Chỉ người được thêm", icon: Lock, tone: "slate" },
  internal: { label: "Nội bộ", short: "Phòng ban được chọn", icon: Building2, tone: "blue" },
  public: { label: "Toàn hệ thống", short: "Mọi người dùng", icon: Earth, tone: "teal" },
};

export const SHARE_MODE_ORDER: ShareMode[] = ["private", "internal", "public"];

export function asShareMode(value: string | null | undefined): ShareMode {
  return value === "private" || value === "public" ? value : "internal";
}
