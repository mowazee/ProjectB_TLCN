import { ClipboardCheck } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";

import type { BulkReviewOut } from "@/shared/api/types";
import { Badge, EmptyState, ErrorBox, Field, Loading, Modal, PageHeader, Pagination } from "@/shared/components/ui";
import { ValidityBadge } from "@/shared/components/validity";
import { APPROVAL_LABELS, formatDateTime } from "@/shared/lib/format";

import { useBulkReview, useReviews, type BulkReviewInput } from "./api";

const BULK_MAX = 20;

const BULK_LABELS: Record<BulkReviewInput["action"], string> = {
  approve: "Duyệt",
  approve_publish: "Duyệt và xuất bản",
  publish: "Xuất bản",
  reject: "Từ chối",
};

const CHECKLIST = [
  { id: "validity", label: "Hiệu lực của tài liệu đã đúng" },
  { id: "physical_copy", label: "Vị trí bản cứng (hoặc Kho chung) đã đúng" },
  { id: "extraction", label: "Kết quả OCR và trường trích xuất đã kiểm tra" },
  { id: "metadata", label: "Danh mục, tiêu đề, số hiệu đã đúng" },
] as const;

/** P2-01 hàng chờ duyệt + FR-20 (SDD v0.14): tích chọn tối đa 20 tài liệu để duyệt / duyệt và xuất bản / từ chối;
 *  duyệt phải tích đủ checklist, từ chối nhập lý do chung. Server xử lý từng tài liệu như thao tác lẻ. */
export function ReviewsPage() {
  const [page, setPage] = useState(1);
  const [showExpired, setShowExpired] = useState(false); // FR-19
  const reviews = useReviews(page, showExpired);
  const bulk = useBulkReview();
  const [selected, setSelected] = useState<string[]>([]);
  const [action, setAction] = useState<BulkReviewInput["action"] | null>(null);
  const [checks, setChecks] = useState<string[]>([]);
  const [comments, setComments] = useState("");
  const [result, setResult] = useState<BulkReviewOut | null>(null);

  const items = reviews.data?.items ?? [];
  const titles = new Map(items.map((r) => [r.document_id, r.title]));
  const toggle = (id: string) =>
    setSelected((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id].slice(0, BULK_MAX)));
  const pageIds = items.map((r) => r.document_id).slice(0, BULK_MAX);
  const allSelected = pageIds.length > 0 && pageIds.every((id) => selected.includes(id));
  const close = () => {
    setAction(null);
    setChecks([]);
    setComments("");
    bulk.reset();
  };
  const confirm = () => {
    if (!action) return;
    bulk.mutate(
      {
        action,
        document_ids: selected,
        comments: comments.trim() || undefined,
        confirmed_checks: action === "reject" ? [] : checks,
      },
      {
        onSuccess: (out) => {
          setResult(out);
          setSelected([]);
          close();
        },
      },
    );
  };
  const ready = action === "reject" ? comments.trim().length > 0 : CHECKLIST.every((c) => checks.includes(c.id));

  return (
    <div>
      <PageHeader
        icon={ClipboardCheck}
        title="Hàng chờ duyệt"
        subtitle={`Tài liệu ở trạng thái “${APPROVAL_LABELS.pending_review}”`}
      />
      <div className="row" style={{ marginBottom: 12, flexWrap: "wrap" }}>
        <span className="muted">
          Đã chọn {selected.length}/{BULK_MAX}
        </span>
        {(["approve", "approve_publish", "reject"] as const).map((a) => (
          <button
            key={a}
            className={`btn ${a === "reject" ? "btn-danger" : "btn-primary"}`}
            disabled={selected.length === 0}
            onClick={() => setAction(a)}
          >
            {BULK_LABELS[a]} ({selected.length})
          </button>
        ))}
        <label className="row">
          <input
            type="checkbox"
            checked={showExpired}
            onChange={(e) => {
              setShowExpired(e.target.checked);
              setPage(1);
            }}
          />
          Hiện tài liệu hết hiệu lực
        </label>
      </div>
      <ErrorBox error={reviews.error} />
      {result && (
        <div className="card" role="status" style={{ marginBottom: 12 }}>
          <div className="row">
            <strong>Kết quả:</strong>
            <Badge tone="ok">{result.succeeded} thành công</Badge>
            {result.failed > 0 && <Badge tone="danger">{result.failed} lỗi</Badge>}
            <button className="btn" onClick={() => setResult(null)}>
              Đóng
            </button>
          </div>
          {result.failed > 0 && (
            <ul>
              {result.results
                .filter((r) => !r.ok)
                .map((r) => (
                  <li key={r.document_id}>
                    {titles.get(r.document_id) ?? r.document_id}: {r.error_message}
                  </li>
                ))}
            </ul>
          )}
        </div>
      )}
      {reviews.isPending ? (
        <Loading />
      ) : !items.length ? (
        <EmptyState>Không có tài liệu chờ duyệt.</EmptyState>
      ) : (
        <>
          <table className="table">
            <thead>
              <tr>
                <th>
                  <input
                    type="checkbox"
                    aria-label="Chọn tất cả trên trang"
                    checked={allSelected}
                    onChange={() => setSelected(allSelected ? selected.filter((id) => !pageIds.includes(id)) : pageIds)}
                  />
                </th>
                <th>Tài liệu</th>
                <th>Hiệu lực</th>
                <th>Người gửi</th>
                <th>Gửi lúc</th>
              </tr>
            </thead>
            <tbody>
              {items.map((r) => (
                <tr key={r.document_id}>
                  <td>
                    <input
                      type="checkbox"
                      aria-label={`Chọn ${r.title}`}
                      checked={selected.includes(r.document_id)}
                      disabled={!selected.includes(r.document_id) && selected.length >= BULK_MAX}
                      onChange={() => toggle(r.document_id)}
                    />
                  </td>
                  <td>
                    <Link to={`/documents/${r.document_id}`} state={{ from: "/reviews", fromLabel: "hàng chờ duyệt" }}>
                      {r.title}
                    </Link>
                  </td>
                  <td>
                    <ValidityBadge status={r.validity_status} validUntil={r.valid_until} />
                  </td>
                  <td>{r.submitted_by ?? "—"}</td>
                  <td>{formatDateTime(r.submitted_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <Pagination
            page={page}
            pageSize={reviews.data?.page_size ?? 20}
            total={reviews.data?.total ?? 0}
            onChange={setPage}
          />
        </>
      )}
      {action && (
        <Modal
          title={`${BULK_LABELS[action]} ${selected.length} tài liệu`}
          onClose={close}
          actions={
            <>
              <button className="btn" onClick={close}>
                Kiểm tra lại
              </button>
              <button
                className={`btn ${action === "reject" ? "btn-danger" : "btn-primary"}`}
                onClick={confirm}
                disabled={!ready || bulk.isPending}
              >
                Xác nhận
              </button>
            </>
          }
        >
          <ErrorBox error={bulk.error} />
          <ul>
            {selected.map((id) => {
              const r = items.find((x) => x.document_id === id);
              return (
                <li key={id}>
                  {r?.title ?? id} {r && <ValidityBadge status={r.validity_status} validUntil={r.valid_until} />}
                </li>
              );
            })}
          </ul>
          {action === "reject" ? (
            <Field label="Lý do từ chối chung (bắt buộc)" htmlFor="bulk-reason">
              <textarea
                id="bulk-reason"
                className="textarea"
                rows={3}
                value={comments}
                onChange={(e) => setComments(e.target.value)}
              />
            </Field>
          ) : (
            <fieldset className="stack" style={{ border: 0, padding: 0, margin: 0 }}>
              <legend>
                <strong>Xác nhận bạn đã kiểm tra các tài liệu trên:</strong>
              </legend>
              {CHECKLIST.map((c) => (
                <label key={c.id} className="row">
                  <input
                    type="checkbox"
                    checked={checks.includes(c.id)}
                    onChange={(e) =>
                      setChecks((cur) => (e.target.checked ? [...cur, c.id] : cur.filter((x) => x !== c.id)))
                    }
                  />
                  {c.label}
                </label>
              ))}
            </fieldset>
          )}
        </Modal>
      )}
    </div>
  );
}
