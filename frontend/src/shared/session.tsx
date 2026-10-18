/**
 * Phiên đăng nhập phía React: lấy từ GET /api/auth/me (cookie HttpOnly, không lưu token ở localStorage).
 * features = danh sách cờ P2 đang bật -> UI registry quyết định route/menu hiển thị (SDD mục 13).
 */
import { useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { api, ApiError, onUnauthorized, setCsrfToken } from "./api/client";
import type { Session } from "./api/types";

export const SESSION_KEY = ["session"] as const;

export async function fetchSession(): Promise<Session | null> {
  try {
    return await api<Session>("/api/auth/me", { silent401: true });
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return null;
    throw err;
  }
}

/**
 * Đổi phiên (login/logout): ghi session mới và xóa mọi dữ liệu server khác của phiên cũ.
 * Không dùng client.clear(): nó xóa cả query session đang được SessionProvider theo dõi.
 */
export function replaceSession(client: QueryClient, session: Session | null): void {
  setCsrfToken(session?.csrf_token ?? null);
  client.setQueryData(SESSION_KEY, session);
  client.removeQueries({ predicate: (q) => q.queryKey[0] !== SESSION_KEY[0] });
}

interface SessionValue {
  session: Session | null;
  /** Id người dùng của phiên gần nhất trong tab này (giữ lại sau logout/hết phiên) - xem RequireAuth/LoginPage. */
  lastUserId: string | null;
  loading: boolean;
  roles: string[];
  features: string[];
  hasRole: (...roles: string[]) => boolean;
  hasFeature: (feature: string) => boolean;
}

const SessionContext = createContext<SessionValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const client = useQueryClient();
  const query = useQuery({ queryKey: SESSION_KEY, queryFn: fetchSession, staleTime: 5 * 60_000, retry: 1 });
  const session = query.data ?? null;
  const [lastUserId, setLastUserId] = useState<string | null>(null);
  if (session && session.user.id !== lastUserId) setLastUserId(session.user.id); // cập nhật state khi render (mẫu React)

  useEffect(() => {
    setCsrfToken(session?.csrf_token ?? null);
  }, [session?.csrf_token]);

  useEffect(
    () =>
      onUnauthorized(() => {
        setCsrfToken(null);
        client.setQueryData(SESSION_KEY, null);
      }),
    [client],
  );

  const value = useMemo<SessionValue>(() => {
    const roles = session?.roles ?? [];
    const features = session?.features ?? [];
    return {
      session,
      lastUserId,
      loading: query.isPending,
      roles,
      features,
      hasRole: (...r) => roles.includes("ADMIN") || r.some((x) => roles.includes(x)),
      hasFeature: (f) => features.includes(f),
    };
  }, [session, lastUserId, query.isPending]);

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession phải nằm trong SessionProvider");
  return ctx;
}
