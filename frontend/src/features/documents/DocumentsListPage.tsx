import { FileText, Trash2, Upload } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useLocation, useSearchParams } from "react-router";

import {
  ApprovalBadge,
  Badge,
  EmptyState,
  ErrorBox,
  JobBadge,
  Loading,
  PageHeader,
  Pagination,
} from "@/shared/components/ui";
import { useCategories } from "@/shared/hooks/useCategories";
import { useDebounce } from "@/shared/hooks/useDebounce";
import { APPROVAL_LABELS, formatDateTime } from "@/shared/lib/format";
import { useSession } from "@/shared/session";

import { useDocuments } from "./api";
import { useRememberListSearch } from "./backLink";
import s from "./documents.module.css";

const STATUS_OPTIONS = [
  ["", "Mọi trạng thái"],
  ["queued", "Đang chờ OCR"],
  ["processing", "Đang xử lý"],
  ["completed", "Hoàn tất"],
  ["failed", "Lỗi"],
  ["needs_review", "Có trang cần xem lại"],
] as const;

export function DocumentsListPage() {
  const [params, setParams] = useSearchParams();
  const page = Number(params.get("page") ?? 1);
  const [q, setQ] = useState(params.get("q") ?? "");
  const debouncedQ = useDebounce(q);
  const urlQ = params.get("q") ?? "";
  // Từ khóa (đã debounce) nằm trên URL như các bộ lọc khác: nút quay lại ở trang chi tiết giữ được nó
  useEffect(() => {
    if (debouncedQ === urlQ) return;
    const next = new URLSearchParams(params);
    if (debouncedQ) next.set("q", debouncedQ);
    else next.delete("q");
    next.delete("page");
    setParams(next, { replace: true });
  }, [debouncedQ, urlQ, params, setParams]);
  const categoryId = params.get("category_id");
  const status = params.get("status") ?? "";
  const approval = params.get("approval_status") ?? "";
  const { hasRole, hasFeature } = useSession();
  const workflow = hasFeature("workflow"); // FR-07 (v0.7): cột + bộ lọc trạng thái duyệt khi quy trình duyệt bật
  useRememberListSearch(useLocation().search);
  const categories = useCategories();
  const list = useDocuments({
    page,
    page_size: 20,
    q: urlQ || undefined,
    category_id: categoryId ? Number(categoryId) : undefined,
    status: status || undefined,
    approval_status: (workflow && approval) || undefined,
  });

  const update = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== "page") next.delete("page");
    setParams(next, { replace: true });
  };

  return (
    <div>
      <PageHeader
        icon={FileText}
        title="Tài liệu"
        subtitle="Tài liệu trong phạm vi quyền của bạn"
        actions={
          <>
            {hasRole("OFFICER") && (
              <Link className="btn" to="/documents/trash">
                <Trash2 size={16} aria-hidden /> Thùng rác
              </Link>
            )}
            {hasRole("OFFICER") && (
              <Link className="btn btn-primary" to="/documents/new">
                <Upload size={16} aria-hidden /> Tải lên
              </Link>
            )}
          </>
        }
      />
      <div className={s.filters}>
        <input
          className="input"
          placeholder="Tìm theo tên tài liệu..."
          value={q}
          onChange={(e) => setQ(e.target.value)}
          aria-label="Tìm theo tên"
        />
        <select
          className="select"
          value={categoryId ?? ""}
          onChange={(e) => update("category_id", e.target.value)}
          aria-label="Danh mục"
        >
          <option value="">Mọi danh mục</option>
          {categories.data?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
              {c.is_active ? "" : " (ngừng dùng)"}
            </option>
          ))}
        </select>
        <select
          className="select"
          value={status}
          onChange={(e) => update("status", e.target.value)}
          aria-label="Trạng thái"
        >
          {STATUS_OPTIONS.map(([v, label]) => (
            <option key={v} value={v}>
              {label}
            </option>
          ))}
        </select>
        {workflow && (
          <select
            className="select"
            value={approval}
            onChange={(e) => update("approval_status", e.target.value)}
            aria-label="Trạng thái duyệt"
          >
            <option value="">Mọi trạng thái duyệt</option>
            {Object.entries(APPROVAL_LABELS).map(([v, label]) => (
              <option key={v} value={v}>
                {label}
              </option>
            ))}
          </select>
        )}
        <Link className="btn" to="/search">
          Tìm trong nội dung
        </Link>
      </div>
      <ErrorBox error={list.error} />
      {list.isPending ? (
        <Loading />
      ) : list.data && list.data.items.length === 0 ? (
        <EmptyState>Chưa có tài liệu nào phù hợp.</EmptyState>
      ) : (
        list.data && (
          <>
            <table className="table">
              <thead>
                <tr>
                  <th>Tài liệu</th>
                  <th>Danh mục</th>
                  <th>Người tải</th>
                  <th>Trang</th>
                  <th>OCR</th>
                  {workflow && <th>Duyệt</th>}
                  <th>Ngày tạo</th>
                </tr>
              </thead>
              <tbody>
                {list.data.items.map((d) => (
                  <tr key={d.id}>
                    <td>
                      <Link className={s.title} to={`/documents/${d.id}`}>
                        {d.title}
                      </Link>
                      <div className="muted">
                        {d.file_type} · {d.file_name}
                      </div>
                    </td>
                    <td>{d.category.name}</td>
                    <td>{d.owner?.full_name ?? "—"}</td>
                    <td>
                      {d.total_pages}
                      {d.needs_review_pages > 0 && (
                        <>
                          {" "}
                          <Badge tone="warn">{d.needs_review_pages} cần xem lại</Badge>
                        </>
                      )}
                    </td>
                    <td>
                      <JobBadge status={d.job_status} />
                    </td>
                    {workflow && (
                      <td>
                        <ApprovalBadge status={d.approval_status} />
                      </td>
                    )}
                    <td>{formatDateTime(d.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pagination
              page={list.data.page}
              pageSize={list.data.page_size}
              total={list.data.total}
              onChange={(p) => update("page", String(p))}
            />
          </>
        )
      )}
    </div>
  );
}
