import { Archive, BookOpenCheck, CalendarClock } from "lucide-react";
import { AdminOnly } from "@/features/admin";
import { lazyNamed } from "@/shared/lib/lazy";
import type { FeatureManifest } from "@/shared/types/feature";

const load = () => import("./pages");
const BorrowRequestsPage = lazyNamed(load, "BorrowRequestsPage");
const StorageLocationsPage = lazyNamed(load, "StorageLocationsPage");

export const borrowingManifest: FeatureManifest = {
  id: "borrowing",
  feature: "borrowing",
  routes: [
    { path: "borrow-requests", element: <BorrowRequestsPage /> },
    {
      path: "admin/storage-locations",
      element: (
        <AdminOnly>
          <StorageLocationsPage />
        </AdminOnly>
      ),
    },
  ],
  nav: [
    { to: "/borrow-requests", label: "Mượn hồ sơ", roles: ["OFFICER", "APPROVER"], order: 40, icon: BookOpenCheck },
    {
      to: "/admin/storage-locations",
      label: "Kho lưu trữ",
      roles: ["ADMIN"],
      group: "admin",
      order: 92,
      icon: Archive,
    },
  ],
  documentTabs: [{ id: "borrow", label: "Mượn hồ sơ", element: lazyNamed(load, "BorrowTab") }],
  dashboardCards: [
    { key: "borrow_pending", label: "Yêu cầu mượn chờ duyệt", to: "/borrow-requests", icon: BookOpenCheck },
    { key: "borrow_overdue", label: "Hồ sơ mượn quá hạn", to: "/borrow-requests", icon: CalendarClock },
  ],
};
