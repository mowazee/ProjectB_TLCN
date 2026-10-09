import { lazyNamed } from "@/shared/lib/lazy";
import type { FeatureManifest } from "@/shared/types/feature";

const load = () => import("./pages");
const ImportPage = lazyNamed(load, "ImportPage");
const ImportReportPage = lazyNamed(load, "ImportReportPage");

export const importsManifest: FeatureManifest = {
  id: "imports",
  feature: "imports",
  routes: [
    { path: "imports", element: <ImportPage /> },
    { path: "imports/:jobId", element: <ImportReportPage /> },
  ],
  nav: [{ to: "/imports", label: "Nhập hàng loạt", roles: ["OFFICER"], order: 15 }],
};
