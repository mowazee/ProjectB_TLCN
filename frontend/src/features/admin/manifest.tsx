import { FolderTree, ScrollText, Users } from "lucide-react";
import type { FeatureManifest } from "@/shared/types/feature";

import { AuditPage } from "./AuditPage";
import { CategoriesPage } from "./CategoriesPage";
import { AdminOnly } from "./AdminOnly";
import { UsersPage } from "./UsersPage";

export const adminManifest: FeatureManifest = {
  id: "admin",
  routes: [
    {
      path: "admin/users",
      element: (
        <AdminOnly>
          <UsersPage />
        </AdminOnly>
      ),
    },
    {
      path: "admin/categories",
      element: (
        <AdminOnly>
          <CategoriesPage />
        </AdminOnly>
      ),
    },
    {
      path: "admin/audit",
      element: (
        <AdminOnly>
          <AuditPage />
        </AdminOnly>
      ),
    },
  ],
  nav: [
    { to: "/admin/users", label: "Người dùng", roles: ["ADMIN"], group: "admin", order: 90, icon: Users },
    { to: "/admin/categories", label: "Danh mục", roles: ["ADMIN"], group: "admin", order: 91, icon: FolderTree },
    { to: "/admin/audit", label: "Nhật ký", roles: ["ADMIN"], group: "admin", order: 93, icon: ScrollText },
  ],
};
