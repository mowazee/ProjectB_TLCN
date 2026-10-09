import { lazyNamed } from "@/shared/lib/lazy";
import type { FeatureManifest } from "@/shared/types/feature";

export const extractionManifest: FeatureManifest = {
  id: "extraction",
  feature: "extraction",
  documentTabs: [
    { id: "fields", label: "Trường trích xuất", element: lazyNamed(() => import("./FieldsTab"), "FieldsTab") },
  ],
};
