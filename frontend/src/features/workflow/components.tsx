import { ClipboardCheck } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";

import {
  ApprovalBadge,
  EmptyState,
  ErrorBox,
  Field,
  Loading,
  Modal,
  PageHeader,
  Pagination,
} from "@/shared/components/ui";
import { APPROVAL_LABELS, formatDateTime } from "@/shared/lib/format";
import type { DocumentSlotProps } from "@/shared/types/feature";

import { useApprovalAction, useApprovalHistory, useApprovalState, useReviews } from "./api";

const ACTION_LABELS: Record<string, string> = {
  submit: "Gửi duyệt",
  approve: "Duyệt",
  reject: "Từ chối",
  publish: "Xuất bản",
  unpublish: "Hủy xuất bản",
  withdraw: "Rút lại",
  return: "Trả lại cho người tải lên",
};
// Thao tác bắt buộc ghi chú: lý do từ chối, ghi chú khi trả lại (D-11)
const NEEDS_COMMENT = new Set(["reject", "return"]);
const HINTS: Record<string, string> = {
  withdraw: "Tài liệu về Nháp để bạn chỉnh sửa (kể cả chạy lại OCR) rồi gửi duyệt lại.",
  unpublish: "Sau khi hủy xuất bản, Kiểm duyệt viên/Admin có thể chỉnh sửa hoặc trả lại cho người tải lên.",
  return: "Tài liệu về Nháp; người tải lên nhận thông báo kèm ghi chú và chỉnh sửa lại.",
};

/** P2-01: nút theo action server cho phép (D-11: gửi duyệt, rút lại - chủ sở hữu; duyệt, xuất bản, hủy, trả lại -
 *  Kiểm duyệt viên phòng ban / Admin); server vẫn kiểm state machine (409) và quyền (403). */
export function ApprovalActions({ document }: DocumentSlotProps) {
  const state = useApprovalState(document.id);
  const action = useApprovalAction(document.id);
  const [pending, setPending] = useState<string | null>(null);
  const [comments, setComments] = useState("");
  if (!state.data) return null;

  const run = (name: string) => {
    action.mutate(
      { action: name, comments: comments.trim() || undefined },
      {
        onSuccess: () => {
          setPending(null);
          setComments("");
        },
      },
    );
  };

  return (
    <>
      <ApprovalBadge status={state.data.approval_status} />
      {state.data.allowed_actions.map((a) => (
        <button
          key={a}
          className={`btn ${a === "approve" || a === "publish" ? "btn-primary" : a === "reject" ? "btn-danger" : ""}`}
          onClick={() => setPending(a)}
        >
          {ACTION_LABELS[a] ?? a}
        </button>
      ))}
      {pending && (
        <Modal
          title={`${ACTION_LABELS[pending]}: ${document.title}`}
          onClose={() => {
            setPending(null);
            action.reset();
          }}
          actions={
            <button
              className="btn btn-primary"
              onClick={() => run(pending)}
              disabled={action.isPending || (NEEDS_COMMENT.has(pending) && !comments.trim())}
            >
              Xác nhận
            </button>
          }
        >
          <ErrorBox error={action.error} />
          {HINTS[pending] && <p className="muted">{HINTS[pending]}</p>}
          <Field
            label={
              pending === "reject"
                ? "Lý do từ chối (bắt buộc)"
                : pending === "return"
                  ? "Ghi chú cho người tải lên (bắt buộc)"
                  : "Ghi chú"
            }
            htmlFor="cm"
          >
            <textarea
              id="cm"
              className="textarea"
              rows={3}
              value={comments}
              onChange={(e) => setComments(e.target.value)}
            />
          </Field>
        </Modal>
      )}
    </>
  );
}

export function ApprovalHistoryTab({ document }: DocumentSlotProps) {
  const history = useApprovalHistory(document.id);
  if (history.isPending) return <Loading />;
  if (history.error) return <ErrorBox error={history.error} />;
  if (!history.data?.length) return <EmptyState>Chưa có lịch sử duyệt.</EmptyState>;
  return (
    <table className="table">
      <thead>
        <tr>
          <th>Thời gian</th>
          <th>Thao tác</th>
          <th>Người thực hiện</th>
          <th>Ghi chú</th>
        </tr>
      </thead>
      <tbody>
        {history.data.map((h) => (
          <tr key={h.id}>
            <td>{formatDateTime(h.created_at)}</td>
            <td>{ACTION_LABELS[h.action] ?? h.action}</td>
            <td>{h.actor_name ?? "—"}</td>
            <td>{h.comments ?? ""}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function ReviewsPage() {
  const [page, setPage] = useState(1);
  const reviews = useReviews(page);
  return (
    <div>
      <PageHeader
        icon={ClipboardCheck}
        title="Hàng chờ duyệt"
        subtitle={`Tài liệu ở trạng thái “${APPROVAL_LABELS.pending_review}”`}
      />
      <ErrorBox error={reviews.error} />
      {reviews.isPending ? (
        <Loading />
      ) : !reviews.data?.items.length ? (
        <EmptyState>Không có tài liệu chờ duyệt.</EmptyState>
      ) : (
        <>
          <table className="table">
            <thead>
              <tr>
                <th>Tài liệu</th>
                <th>Người gửi</th>
                <th>Gửi lúc</th>
              </tr>
            </thead>
            <tbody>
              {reviews.data.items.map((r) => (
                <tr key={r.document_id}>
                  <td>
                    <Link to={`/documents/${r.document_id}`} state={{ from: "/reviews", fromLabel: "hàng chờ duyệt" }}>
                      {r.title}
                    </Link>
                  </td>
                  <td>{r.submitted_by ?? "—"}</td>
                  <td>{formatDateTime(r.submitted_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <Pagination page={page} pageSize={reviews.data.page_size} total={reviews.data.total} onChange={setPage} />
        </>
      )}
    </div>
  );
}
