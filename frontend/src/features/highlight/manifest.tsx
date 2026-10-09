import { lazyNamed } from "@/shared/lib/lazy";
import type { FeatureManifest } from "@/shared/types/feature";

export const highlightManifest: FeatureManifest = {
  id: "highlight",
  feature: "highlight",
  pageOverlays: [lazyNamed(() => import("./HighlightOverlay"), "HighlightOverlay")],
};
