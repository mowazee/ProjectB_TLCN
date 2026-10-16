import { Search } from "lucide-react";
import type { FeatureManifest } from "@/shared/types/feature";

import { SearchPage } from "./SearchPage";

export const searchManifest: FeatureManifest = {
  id: "search",
  routes: [{ path: "search", element: <SearchPage /> }],
  nav: [{ to: "/search", label: "Tìm kiếm", order: 20, icon: Search }],
};
