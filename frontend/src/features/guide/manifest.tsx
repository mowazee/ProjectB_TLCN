import { BookOpen } from "lucide-react";

import { lazyNamed } from "@/shared/lib/lazy";
import type { FeatureManifest } from "@/shared/types/feature";

const GuidePage = lazyNamed(() => import("./GuidePage"), "GuidePage");

/** Hướng dẫn sử dụng (v0.14, lõi): mọi người dùng đã đăng nhập. */
export const guideManifest: FeatureManifest = {
  id: "guide",
  routes: [{ path: "guide", element: <GuidePage /> }],
  nav: [{ to: "/guide", label: "Hướng dẫn sử dụng", group: "personal", order: 90, icon: BookOpen }],
};
