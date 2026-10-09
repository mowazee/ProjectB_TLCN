import type { ReactNode } from "react";

import { RequireAuth } from "@/features/auth";

/** Route guard cho trang quản trị (server vẫn trả 403 nếu không phải Admin). */
export function AdminOnly({ children }: { children: ReactNode }) {
  return <RequireAuth roles={["ADMIN"]}>{children}</RequireAuth>;
}
