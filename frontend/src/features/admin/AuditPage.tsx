import { ScrollText } from "lucide-react";
import { Fragment, useState } from "react";
import { Link, useSearchParams } from "react-router";

import { Badge, EmptyState, ErrorBox, Loading, PageHeader, Pagination } from "@/shared/components/ui";
import { formatDateTime } from "@/shared/lib/format";
import { SlotList, useSlots } from "@/shared/slots";

import { useAudit } from "./api";

/** UC-08 (FR-08): chỉ Admin; lọc theo ngày/người/tài liệu/hành động; log chỉ đọc (P2-09 rollback cắm vào slot). */
export function AuditPage() {
  // Bộ lọc ban đầu lấy từ URL: vd. /admin/audit?user_id=… từ trang Người dùng/Nhóm quyền (FR-01)
  const [params] = useSearchParams();
  const [filters, setFilters] = useState({
    date_from: "",
    date_to: "",
    user_id: params.get("user_id") ?? "",
    document_id: params.get("document_id") ?? "",
    action: params.get("action") ?? "",
  });
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState<number | null>(null);
  const audit = useAudit({ ...filters, page });
  const { auditRowActions } = useSlots();
  const set = (k: keyof typeof filters, v: string) => {
    setFilters((f) => ({ ...f, [k]: v }));
    setPage(1);
  };

  return (
    <div>
      <PageHeader
        icon={ScrollText}
        title="Nhật ký hệ thống"
        subtitle="Nhật ký chỉ ghi thêm, không sửa/xóa từ giao diện."
      />
      <div className="row" style={{ marginBottom: 12 }}>
        <label className="row">
          Từ{" "}
          <input
            className="input"
            type="date"
            value={filters.date_from}
            onChange={(e) => set("date_from", e.target.value)}
          />
        </label>
        <label className="row">
          Đến{" "}
          <input
            className="input"
            type="date"
            value={filters.date_to}
            onChange={(e) => set("date_to", e.target.value)}
          />
        </label>
        <input
          className="input"
          style={{ maxWidth: 200 }}
          placeholder="Hành động (vd. edit_ocr)"
          value={filters.action}
          onChange={(e) => set("action", e.target.value)}
        />
        <input
          className="input"
          style={{ maxWidth: 300 }}
          placeholder="ID người dùng"
          value={filters.user_id}
          onChange={(e) => set("user_id", e.target.value.trim())}
        />
        <input
          className="input"
          style={{ maxWidth: 300 }}
          placeholder="ID tài liệu"
          value={filters.document_id}
          onChange={(e) => set("document_id", e.target.value.trim())}
        />
      </div>
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
                    <td>
                      {log.entity_type ?? "—"}
                      {log.document_id && (
                        <div>
                          <Link to={`/documents/${log.document_id}`}>tài liệu</Link>
                        </div>
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
                      <td colSpan={7}>
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
