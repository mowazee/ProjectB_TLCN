import { FileText, Trash2 } from "lucide-react";
import type { FeatureManifest } from "@/shared/types/feature";

import { DocumentDetailPage } from "./DocumentDetailPage";
import { DocumentsListPage } from "./DocumentsListPage";
import { TrashPage } from "./TrashPage";
import { UploadPage } from "./UploadPage";

export const documentsManifest: FeatureManifest = {
  id: "documents",
  routes: [
    { path: "documents", element: <DocumentsListPage /> },
    { path: "documents/new", element: <UploadPage /> },
    { path: "documents/trash", element: <TrashPage /> },
    { path: "documents/:id", element: <DocumentDetailPage /> },
  ],
  nav: [
    { to: "/documents", label: "Tài liệu", group: "documents", order: 10, icon: FileText },
    { to: "/documents/trash", label: "Thùng rác", roles: ["OFFICER"], group: "documents", order: 26, icon: Trash2 },
  ],
};
