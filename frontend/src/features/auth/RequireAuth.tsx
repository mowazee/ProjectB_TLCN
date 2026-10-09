import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router";

import { Loading } from "@/shared/components/ui";
import { useSession } from "@/shared/session";

/** Route guard chỉ cải thiện trải nghiệm; server mới là nơi quyết định quyền (SDD mục 14). */
export function RequireAuth({ children, roles }: { children: ReactNode; roles?: string[] }) {
  const { session, loading, hasRole } = useSession();
  const location = useLocation();
  if (loading) return <Loading />;
  if (!session) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  if (roles && !hasRole(...roles)) {
    return (
      <div className="card">
        <h2>Không có quyền truy cập</h2>
        <p className="muted">Tài khoản của bạn không được phép xem trang này.</p>
      </div>
    );
  }
  return <>{children}</>;
}
