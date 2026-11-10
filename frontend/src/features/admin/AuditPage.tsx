import { ScrollText } from "lucide-react";
import { Fragment, useState } from "react";
import { Link, useSearchParams } from "react-router";

import { Badge, EmptyState, ErrorBox, Field, Loading, PageHeader, Pagination } from "@/shared/components/ui";
import { useDebounce } from "@/shared/hooks/useDebounce";
import { formatDateTime } from "@/shared/lib/format";
import { SlotList, useSlots } from "@/shared/slots";

import { useAudit } from "./api";

/** UC-08 (FR-08): chỉ Admin; lọc theo ngày, hành động (gần đúng), tên người dùng, tên tài liệu; log chỉ đọc (P2-09 rollback cắm vào slot). */
export function AuditPage() {
  // Bộ lọc ban đầu lấy từ URL: vd. /admin/audit?user_id=… từ trang Người dùng/Nhóm quyền (FR-01). Ô nhập dùng tên
  // (người dùng, tài liệu) và tìm gần đúng - người dùng không cần biết ID (v0.15).
  const [params, setParams] = useSearchParams();
  const [filters, setFilters] = useState({
    date_from: "",
    date_to: "",
    action: params.get("action") ?? "",
    user: "",
    document: "",
  });
  const userId = params.get("user_id") ?? "";
  const documentId = params.get("document_id") ?? "";
  const action = useDebounce(filters.action.trim());
  const user = useDebounce(filters.user.trim());
  const document = useDebounce(filters.document.trim());
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState<number | null>(null);
  const audit = useAudit({
    page,
    date_from: filters.date_from,
    date_to: filters.date_to,
    action,
    user,
    document,
    user_id: userId,
    document_id: documentId,
  });
  const { auditRowActions } = useSlots();
  const set = (k: keyof typeof filters, v: string) => {
    setFilters((f) => ({ ...f, [k]: v }));
    setPage(1);
  };
  const clearLinked = () => {
    const next = new URLSearchParams(params);
    next.delete("user_id");
    next.delete("document_id");
    setParams(next, { replace: true });
    setPage(1);
  };

  return (
    <div>
      <PageHeader
        icon={ScrollText}
        title="Nhật ký hệ thống"
        subtitle="Nhật ký chỉ ghi thêm, không sửa/xóa từ giao diện."
      />
      <div
        className="card"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))",
          gap: 12,
          alignItems: "end",
          marginBottom: 12,
        }}
      >
        <Field label="Từ ngày" htmlFor="af-from">
          <input
            id="af-from"
            className="input"
            type="date"
            value={filters.date_from}
            onChange={(e) => set("date_from", e.target.value)}
          />
        </Field>
        <Field label="Đến ngày" htmlFor="af-to">
          <input
            id="af-to"
            className="input"
            type="date"
            value={filters.date_to}
            onChange={(e) => set("date_to", e.target.value)}
          />
        </Field>
        <Field label="Hành động" htmlFor="af-action">
          <input
            id="af-action"
            className="input"
            placeholder="vd. upload, share, ocr"
            value={filters.action}
            onChange={(e) => set("action", e.target.value)}
          />
        </Field>
        <Field label="Người dùng" htmlFor="af-user">
          <input
            id="af-user"
            className="input"
            placeholder="Tên đăng nhập hoặc họ tên"
            value={filters.user}
            onChange={(e) => set("user", e.target.value)}
          />
        </Field>
        <Field label="Tài liệu" htmlFor="af-doc">
          <input
            id="af-doc"
            className="input"
            placeholder="Tên tài liệu"
            value={filters.document}
            onChange={(e) => set("document", e.target.value)}
          />
        </Field>
      </div>
      {(userId || documentId) && (
        <p className="row muted" style={{ marginBottom: 12 }}>
          Đang lọc theo {userId ? "người dùng" : "tài liệu"} được chọn từ trang trước.
          <button className="btn btn-sm" onClick={clearLinked}>
            Bỏ lọc
          </button>
        </p>
      )}
      <ErrorBox error={audit.error} />
      {audit.isPending ? (
        <Loading />
      ) : !audit.data?.items.length ? (
        <EmptyState>Không có bản ghi.</EmptyState>
      ) : (
        <>
          <table className="table">
            <thead>
              <tr>
                <th>Thời gian</th>
                <th>Người thực hiện</th>
                <th>Hành động</th>
                <th>Đối tượng</th>
                <th>Tên tài liệu</th>
                <th>Kết quả</th>
                <th>IP</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {audit.data.items.map((log) => (
                <Fragment key={log.id}>
                  <tr>
                    <td>{formatDateTime(log.created_at)}</td>
                    <td>{log.user_name ?? <span className="muted">Hệ thống</span>}</td>
                    <td>
                      <code>{log.action}</code>
                      <div className="muted">{log.module}</div>
                    </td>
                    <td>{log.entity_type ?? "—"}</td>
                    <td>
                      {log.document_id && log.document_title ? (
                        <Link to={`/documents/${log.document_id}`}>{log.document_title}</Link>
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                    <td>
                      {log.result === "success" ? (
                        <Badge tone="ok">Thành công</Badge>
                      ) : (
                        <Badge tone="danger">Thất bại</Badge>
                      )}
                    </td>
                    <td>{log.ip_address ?? "—"}</td>
                    <td>
                      <div className="row">
                        <button className="btn btn-sm" onClick={() => setOpen(open === log.id ? null : log.id)}>
                          Chi tiết
                        </button>
                        <SlotList items={auditRowActions} props={{ log }} />
                      </div>
                    </td>
                  </tr>
                  {open === log.id && (
                    <tr>
                      <td colSpan={8}>
                        <div className="row" style={{ alignItems: "flex-start" }}>
                          <div className="grow">
                            <strong>Trước</strong>
                            <pre style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(log.state_before, null, 2)}</pre>
                          </div>
                          <div className="grow">
                            <strong>Sau</strong>
                            <pre style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(log.state_after, null, 2)}</pre>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
          <Pagination page={page} pageSize={audit.data.page_size} total={audit.data.total} onChange={setPage} />
        </>
      )}
    </div>
  );
}
