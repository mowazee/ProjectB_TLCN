/**
 * Hợp đồng UI registry (Đặc tả đề tài v0.5 mục 4.3, 4.6): mỗi feature khai báo manifest; lõi chỉ render slot.
 * Feature P2 cắm vào slot (tab chi tiết tài liệu, lớp phủ PageViewer, công cụ OCR Editor...) mà không sửa
 * page của feature lõi.
 */
import type { LucideIcon } from "lucide-react";
import type { ComponentType, LazyExoticComponent } from "react";
import type { RouteObject } from "react-router";

import type { AuditLog, DocumentOut } from "@/shared/api/types";

type Slot<P> = ComponentType<P> | LazyExoticComponent<ComponentType<P>>;

export type NavGroup = "main" | "documents" | "workflow" | "admin" | "personal";

export interface NavItem {
  to: string;
  label: string;
  /** Vai trò được thấy mục menu (không có = mọi người dùng đã đăng nhập). Server vẫn kiểm quyền. */
  roles?: string[];
  order?: number;
  /** Nhóm trên sidebar (v0.7): main = Tổng quan (không tiêu đề), mặc định main. */
  group?: NavGroup;
  /** Icon lucide-react hiển thị cạnh nhãn menu. */
  icon?: LucideIcon;
}

export interface DocumentSlotProps {
  document: DocumentOut;
}

export interface DocumentTab {
  id: string;
  label: string;
  element: Slot<DocumentSlotProps>;
}

export interface PageOverlayProps {
  documentId: string;
  pageNumber: number;
  /** Kích thước ảnh trang gốc (pixel) và tỉ lệ đang hiển thị. */
  imageWidth: number;
  imageHeight: number;
  scale: number;
  /** Từ khóa tìm kiếm (?q=) khi mở từ kết quả tìm kiếm. */
  query: string;
}

export interface EditorToolProps {
  documentId: string;
  pageNumber: number;
  currentVersion: number;
}

export interface AuditRowProps {
  log: AuditLog;
}

export interface FeatureManifest {
  id: string;
  /** Cờ P2 (FEATURES_ENABLED); không có = lõi MVP, luôn bật. */
  feature?: string;
  /** Route nằm trong layout đã đăng nhập. */
  routes?: RouteObject[];
  nav?: NavItem[];
  documentTabs?: DocumentTab[];
  /** Nút thao tác trên trang chi tiết tài liệu (duyệt, chạy lại OCR...). */
  documentActions?: Slot<DocumentSlotProps>[];
  pageOverlays?: Slot<PageOverlayProps>[];
  editorTools?: Slot<EditorToolProps>[];
  auditRowActions?: Slot<AuditRowProps>[];
  /** Phần tử trên thanh tiêu đề (chuông thông báo). */
  headerItems?: Slot<object>[];
  /** Trường bổ sung trong form upload (render input có name, gửi kèm FormData). */
  uploadFields?: Slot<object>[];
  /** Thẻ bổ sung trên dashboard, đọc từ stats.extras. */
  dashboardCards?: { key: string; label: string; to?: string; icon?: LucideIcon }[];
}
