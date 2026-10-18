import { ClipboardCheck } from "lucide-react";
import { lazyNamed } from "@/shared/lib/lazy";
import type { FeatureManifest } from "@/shared/types/feature";

const load = () => import("./components");
const ReviewsPage = lazyNamed(load, "ReviewsPage");

export const workflowManifest: FeatureManifest = {
  id: "workflow",
  feature: "workflow",
  routes: [{ path: "reviews", element: <ReviewsPage /> }],
  nav: [
    {
      to: "/reviews",
      label: "Duyệt tài liệu",
      roles: ["APPROVER"],
      group: "workflow",
      order: 30,
      icon: ClipboardCheck,
    },
  ],
  documentActions: [lazyNamed(load, "ApprovalActions")],
  documentTabs: [{ id: "approvals", label: "Lịch sử duyệt", element: lazyNamed(load, "ApprovalHistoryTab") }],
  dashboardCards: [
    { key: "documents_pending_review", label: "Tài liệu chờ duyệt", to: "/reviews", icon: ClipboardCheck },
  ],
};
