import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";

import { api } from "@/shared/api/client";
import type { NotificationPage } from "@/shared/api/types";
import { formatDateTime } from "@/shared/lib/format";

import s from "./notifications.module.css";

const POLL_MS = 30_000; // SDD mục 13: thông báo P2-07 lấy bằng polling nhẹ

function linkFor(type: string): string {
  if (type === "approval.submit") return "/reviews";
  if (type.startsWith("borrow.")) return "/borrow-requests";
  return "/documents";
}

export function NotificationBell() {
  const client = useQueryClient();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const data = useQuery({
    queryKey: ["notifications"],
    queryFn: () => api<NotificationPage>("/api/notifications", { query: { page_size: 10 } }),
    refetchInterval: POLL_MS,
  });
  const invalidate = () => client.invalidateQueries({ queryKey: ["notifications"] });
  const read = useMutation({
    mutationFn: (id: string) => api(`/api/notifications/${id}/read`, { method: "POST" }),
    onSuccess: invalidate,
  });
  const readAll = useMutation({
    mutationFn: () => api("/api/notifications/read-all", { method: "POST" }),
    onSuccess: invalidate,
  });

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  const unread = data.data?.unread ?? 0;
  return (
    <div className={s.wrap} ref={ref}>
      <button className={`btn ${s.bell}`} onClick={() => setOpen(!open)} aria-label={`Thông báo (${unread} chưa đọc)`}>
        🔔{unread > 0 && <span className={s.count}>{unread > 99 ? "99+" : unread}</span>}
      </button>
      {open && (
        <div className={s.panel}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <strong>Thông báo</strong>
            {unread > 0 && (
              <button className="btn btn-sm" onClick={() => readAll.mutate()}>
                Đánh dấu đã đọc hết
              </button>
            )}
          </div>
          {!data.data?.items.length ? (
            <p className="muted">Không có thông báo.</p>
          ) : (
            <ul className={s.list}>
              {data.data.items.map((n) => (
                <li key={n.id} className={n.is_read ? s.read : ""}>
                  <Link
                    to={linkFor(n.type)}
                    onClick={() => {
                      if (!n.is_read) read.mutate(n.id);
                      setOpen(false);
                    }}
                  >
                    {n.title}
                  </Link>
                  <div className="muted">{formatDateTime(n.created_at)}</div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
