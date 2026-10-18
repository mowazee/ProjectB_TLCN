import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, CheckCheck } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";

import { api } from "@/shared/api/client";
import type { NotificationPage } from "@/shared/api/types";
import { EmptyState, ErrorBox, Loading, PageHeader, Pagination } from "@/shared/components/ui";
import { formatDateTime } from "@/shared/lib/format";

import { linkFor } from "./link";
import s from "./notifications.module.css";

const PAGE_SIZE = 20;

/** FR-09 (v0.7) + P2-07: toàn bộ thông báo của người dùng, phân trang, lọc chưa đọc. */
export function NotificationsPage() {
  const client = useQueryClient();
  const [page, setPage] = useState(1);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const data = useQuery({
    queryKey: ["notifications", "page", page, unreadOnly],
    queryFn: () =>
      api<NotificationPage>("/api/notifications", { query: { page, page_size: PAGE_SIZE, unread_only: unreadOnly } }),
    placeholderData: (prev) => prev,
  });
  // khóa ["notifications"] gồm cả chuông thông báo trên thanh tiêu đề
  const invalidate = () => client.invalidateQueries({ queryKey: ["notifications"] });
  const read = useMutation({
    mutationFn: (id: string) => api(`/api/notifications/${id}/read`, { method: "POST" }),
    onSuccess: invalidate,
  });
  const readAll = useMutation({
    mutationFn: () => api("/api/notifications/read-all", { method: "POST" }),
    onSuccess: invalidate,
  });
  const unread = data.data?.unread ?? 0;

  return (
    <div>
      <PageHeader
        icon={Bell}
        title="Thông báo"
        subtitle={`${unread} chưa đọc`}
        actions={
          <button className="btn" disabled={!unread || readAll.isPending} onClick={() => readAll.mutate()}>
            <CheckCheck size={16} aria-hidden /> Đánh dấu đã đọc hết
          </button>
        }
      />
      <label className="row" style={{ marginBottom: 12 }}>
        <input
          type="checkbox"
          checked={unreadOnly}
          onChange={(e) => {
            setUnreadOnly(e.target.checked);
            setPage(1);
          }}
        />
        Chỉ hiện thông báo chưa đọc
      </label>
      <ErrorBox error={data.error ?? read.error ?? readAll.error} />
      {data.isPending ? (
        <Loading />
      ) : !data.data?.items.length ? (
        <EmptyState icon={Bell}>{unreadOnly ? "Không có thông báo chưa đọc." : "Chưa có thông báo."}</EmptyState>
      ) : (
        <>
          <ul className={`card ${s.list} ${s.pageList}`}>
            {data.data.items.map((n) => (
              <li key={n.id} className={n.is_read ? s.read : ""}>
                <div className={s.pageItem}>
                  <div>
                    <Link to={linkFor(n.type, n.link_url)} onClick={() => !n.is_read && read.mutate(n.id)}>
                      {n.title}
                    </Link>
                    {n.message && <div className={s.msg}>{n.message}</div>}
                    <time className={s.time}>{formatDateTime(n.created_at)}</time>
                  </div>
                  {!n.is_read && (
                    <button className="btn btn-ghost btn-sm" onClick={() => read.mutate(n.id)}>
                      Đã đọc
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
          <Pagination page={page} pageSize={data.data.page_size} total={data.data.total} onChange={setPage} />
        </>
      )}
    </div>
  );
}
