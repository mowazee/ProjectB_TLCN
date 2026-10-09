import { useState } from "react";
import { Link } from "react-router";

import { EmptyState, ErrorBox, Loading, PageHeader, Pagination } from "@/shared/components/ui";
import { formatDateTime } from "@/shared/lib/format";

import { useDocuments, useRestoreDocument } from "./api";

/** UC-05b (FR-07, D-05): tài liệu đã xóa mềm, khôi phục trong hạn; quá hạn hệ thống xóa cứng. */
export function TrashPage() {
  const [page, setPage] = useState(1);
  const list = useDocuments({ page, page_size: 20, lifecycle_status: "deleted" });
  const restore = useRestoreDocument();
  const [now] = useState(() => Date.now());

  return (
    <div>
      <PageHeader
        title="Thùng rác"
        subtitle="Tài liệu đã xóa có thể khôi phục trước hạn; quá hạn sẽ bị xóa vĩnh viễn (vẫn giữ nhật ký)."
        actions={
          <Link className="btn" to="/documents">
            ‹ Danh sách tài liệu
          </Link>
        }
      />
      <ErrorBox error={list.error ?? restore.error} />
      {list.isPending ? (
        <Loading />
      ) : !list.data?.items.length ? (
        <EmptyState>Thùng rác trống.</EmptyState>
      ) : (
        <>
          <table className="table">
            <thead>
              <tr>
                <th>Tài liệu</th>
                <th>Danh mục</th>
                <th>Đã xóa lúc</th>
                <th>Hạn khôi phục</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {list.data.items.map((d) => {
                const expired = d.restore_deadline ? new Date(d.restore_deadline).getTime() < now : false;
                return (
                  <tr key={d.id}>
                    <td>{d.title}</td>
                    <td>{d.category.name}</td>
                    <td>{formatDateTime(d.deleted_at)}</td>
                    <td style={expired ? { color: "var(--c-danger)" } : undefined}>
                      {formatDateTime(d.restore_deadline)}
                      {expired && " (đã quá hạn)"}
                    </td>
                    <td>
                      {d.can_edit && !expired && (
                        <button
                          className="btn btn-sm"
                          onClick={() => restore.mutate(d.id)}
                          disabled={restore.isPending}
                        >
                          Khôi phục
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <Pagination page={page} pageSize={list.data.page_size} total={list.data.total} onChange={setPage} />
        </>
      )}
    </div>
  );
}
