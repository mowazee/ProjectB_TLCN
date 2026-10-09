import { lazyNamed } from "@/shared/lib/lazy";
import type { FeatureManifest } from "@/shared/types/feature";

export const classificationManifest: FeatureManifest = {
  id: "classification",
  feature: "classification",
  documentTabs: [
    {
      id: "suggestions",
      label: "Gợi ý danh mục",
      element: lazyNamed(() => import("./SuggestionsTab"), "SuggestionsTab"),
    },
  ],
};
