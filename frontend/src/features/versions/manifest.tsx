import { lazyNamed } from "@/shared/lib/lazy";
import type { FeatureManifest } from "@/shared/types/feature";

export const versionsManifest: FeatureManifest = {
  id: "versions",
  feature: "versions",
  editorTools: [lazyNamed(() => import("./VersionsPanel"), "VersionsPanel")],
};
