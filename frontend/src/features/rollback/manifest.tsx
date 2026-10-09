import { lazyNamed } from "@/shared/lib/lazy";
import type { FeatureManifest } from "@/shared/types/feature";

export const rollbackManifest: FeatureManifest = {
  id: "rollback",
  feature: "rollback",
  auditRowActions: [lazyNamed(() => import("./RollbackButton"), "RollbackButton")],
};
