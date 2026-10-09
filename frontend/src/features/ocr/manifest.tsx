import type { FeatureManifest } from "@/shared/types/feature";

import { EditorPage } from "./EditorPage";
import { PageViewerPage } from "./PageViewerPage";

export const ocrManifest: FeatureManifest = {
  id: "ocr",
  routes: [
    { path: "documents/:id/pages/:page", element: <PageViewerPage /> },
    { path: "documents/:id/pages/:page/edit", element: <EditorPage /> },
  ],
};
