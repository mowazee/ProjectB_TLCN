import type { FeatureManifest } from "@/shared/types/feature";

import { AccountPage } from "./AccountPage";

/** FR-09 (v0.7): lõi, mọi người dùng đã đăng nhập; mở từ khối người dùng trên thanh tiêu đề. */
export const accountManifest: FeatureManifest = {
  id: "account",
  routes: [{ path: "account", element: <AccountPage /> }],
};
