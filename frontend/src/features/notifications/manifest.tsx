import { lazyNamed } from "@/shared/lib/lazy";
import type { FeatureManifest } from "@/shared/types/feature";

const NotificationsPage = lazyNamed(() => import("./NotificationsPage"), "NotificationsPage");

export const notificationsManifest: FeatureManifest = {
  id: "notifications",
  feature: "notifications",
  routes: [{ path: "notifications", element: <NotificationsPage /> }], // FR-09 (v0.7)
  headerItems: [lazyNamed(() => import("./NotificationBell"), "NotificationBell")],
};
