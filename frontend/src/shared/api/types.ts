/** Alias types sinh từ OpenAPI (npm run gen:api); không viết tay kiểu dữ liệu API. */
import type { components } from "./schema";

type S = components["schemas"];

export type Session = S["SessionOut"];
export type UserBrief = S["UserBrief"];
export type User = S["UserOut"];
export type UserIn = S["UserIn"];
export type UserPatch = S["UserPatch"];
export type Role = S["RoleOut"];
export type Department = S["DepartmentOut"];
export type DepartmentIn = S["DepartmentIn"];
export type DepartmentPatch = S["DepartmentPatch"];
export type Account = S["AccountOut"];
export type AccountPatch = S["AccountPatch"];
export type PasswordIn = S["PasswordIn"];
export type Category = S["CategoryOut"];
export type CategoryIn = S["CategoryIn"];
export type CategoryPatch = S["CategoryPatch"];
export type DocumentOut = S["DocumentOut"];
export type DocumentPatch = S["DocumentPatch"];
export type UploadOut = S["UploadOut"];
export type PageSummary = S["PageSummary"];
export type PageDetail = S["PageOut"];
export type OcrBox = S["BoxOut"];
export type CorrectionIn = S["CorrectionIn"];
export type CorrectionOut = S["CorrectionOut"];
export type Job = S["JobOut"];
export type JobListItem = S["JobListItem"];
export type SearchHit = S["SearchHitOut"];
export type PageHit = S["PageHitOut"];
export type Dashboard = S["DashboardOut"];
export type AuditLog = S["AuditLogOut"];

// P2
export type ApprovalState = S["ApprovalStateOut"];
export type ApprovalEntry = S["ApprovalEntryOut"];
export type ReviewItem = S["ReviewItemOut"];
export type Highlights = S["HighlightsOut"];
export type HighlightBox = S["HighlightBoxOut"];
export type VersionInfo = S["VersionOut"];
export type Diff = S["DiffOut"];
export type Fields = S["FieldsOut"];
export type Field = S["FieldOut"];
export type Suggestions = S["SuggestionsOut"];
export type Suggestion = S["SuggestionOut"];
export type Borrow = S["BorrowOut"];
export type BorrowIn = S["BorrowIn"];
export type StorageLocation = S["LocationOut"];
export type NotificationPage = S["NotificationPage"];
export type Notification = S["NotificationOut"];
export type ImportAccepted = S["ImportAccepted"];
export type ImportReport = S["ImportReport"];
export type Rollback = S["RollbackOut"];
export type ReprocessOut = S["ReprocessOut"];

export interface Paged<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}
