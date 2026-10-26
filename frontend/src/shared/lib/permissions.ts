/** D-11 (SDD v0.12): quyền của người dùng hiện tại trên một tài liệu, do server tính (DocumentOut.permissions).
 *  React chỉ dùng để hiện/ẩn nút; server vẫn kiểm từng thao tác và trả 403 kèm lý do. */
export type DocPermission =
  "edit" | "reprocess" | "delete" | "restore" | "cancel_job" | "submit" | "withdraw" | "share";

export function can(doc: { permissions?: string[] | null }, permission: DocPermission): boolean {
  return Boolean(doc.permissions?.includes(permission));
}
