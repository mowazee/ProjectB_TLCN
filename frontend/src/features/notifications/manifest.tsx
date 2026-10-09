import { lazyNamed } from "@/shared/lib/lazy";
import type { FeatureManifest } from "@/shared/types/feature";

export const notificationsManifest: FeatureManifest = {
  id: "notifications",
  feature: "notifications",
  headerItems: [lazyNamed(() => import("./NotificationBell"), "NotificationBell")],
};
