// Thông báo tạo trước SDD v0.6 chưa có link_url: suy từ type như trước
export function linkFor(type: string, linkUrl: string | null): string {
  if (linkUrl?.startsWith("/")) return linkUrl;
  if (type === "approval.submit") return "/reviews";
  if (type.startsWith("borrow.")) return "/borrow-requests";
  return "/documents";
}
