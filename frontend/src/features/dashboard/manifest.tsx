import { LayoutDashboard } from "lucide-react";
import { lazyNamed } from "@/shared/lib/lazy";
import type { FeatureManifest } from "@/shared/types/feature";

const DashboardPage = lazyNamed(() => import("./DashboardPage"), "DashboardPage"); // Chart.js tách chunk

export const dashboardManifest: FeatureManifest = {
  id: "dashboard",
  routes: [{ index: true, element: <DashboardPage /> }],
  nav: [{ to: "/", label: "Tổng quan", order: 0, icon: LayoutDashboard }],
};
