import { lazyNamed } from "@/shared/lib/lazy";
import type { FeatureManifest } from "@/shared/types/feature";

const load = () => import("./components");

export const handwritingManifest: FeatureManifest = {
  id: "handwriting",
  feature: "handwriting",
  uploadFields: [lazyNamed(load, "HandwrittenField")],
  documentActions: [lazyNamed(load, "ReprocessButton")],
};
