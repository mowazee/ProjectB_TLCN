import { Link } from "react-router";

import type { Borrow } from "@/shared/api/types";
import { Badge, ErrorBox } from "@/shared/components/ui";
import { formatDate } from "@/shared/lib/format";
import { useSession } from "@/shared/session";

import { useBorrowMutations } from "./api";

const STATUS: Record<string, [string, "info" | "ok" | "danger" | "neutral"]> = {
  pending: ["Chờ duyệt", "info"],
  approved: ["Đang mượn", "ok"],
  rejected: ["Từ chối", "danger"],
  returned: ["Đã trả", "neutral"],
};

export function BorrowTable({ items, showDocument = true }: { items: Borrow[]; showDocument?: boolean }) {
  const { hasRole } = useSession();
  const { act } = useBorrowMutations();
  const decider = hasRole("APPROVER");
  return (
    <>
      <ErrorBox error={act.error} />
      <table className="table">
        <thead>
          <tr>
            {showDocument && <th>Hồ sơ</th>}
            <th>Người mượn</th>
            <th>Thời gian</th>
            <th>Mục đích</th>
            <th>Trạng thái</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {items.map((b) => {
            const [label, tone] = STATUS[b.status] ?? [b.status, "neutral"];
            return (
              <tr key={b.id}>
                {showDocument && (
                  <td>
                    <Link to={`/documents/${b.document_id}`}>{b.document_title ?? "—"}</Link>
                    <div className="muted">{b.storage_location ?? ""}</div>
                  </td>
                )}
                <td>{b.requester_name ?? "—"}</td>
                <td>
                  {formatDate(b.from_date)} – {formatDate(b.to_date)}
                </td>
                <td>{b.purpose ?? ""}</td>
                <td>
                  <Badge tone={tone}>{label}</Badge> {b.is_overdue && <Badge tone="danger">Quá hạn</Badge>}
                  {b.approver_name && <div className="muted">bởi {b.approver_name}</div>}
                </td>
                <td>
                  <div className="row">
                    {decider && b.status === "pending" && (
                      <>
                        <button
                          className="btn btn-sm btn-primary"
                          disabled={act.isPending}
                          onClick={() => act.mutate({ id: b.id, action: "approve" })}
                        >
                          Duyệt
                        </button>
                        <button
                          className="btn btn-sm btn-danger"
                          disabled={act.isPending}
                          onClick={() => act.mutate({ id: b.id, action: "reject" })}
                        >
                          Từ chối
                        </button>
                      </>
                    )}
                    {decider && b.status === "approved" && (
                      <button
                        className="btn btn-sm"
                        disabled={act.isPending}
                        onClick={() => act.mutate({ id: b.id, action: "return" })}
                      >
                        Ghi nhận trả
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </>
  );
}
