import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { ApiError, api } from "@/shared/api/client";
import type { Rollback } from "@/shared/api/types";
import { ErrorBox, Loading, Modal } from "@/shared/components/ui";
import type { AuditRowProps } from "@/shared/types/feature";

/** Hành động có thể rollback (khớp backend rollback.SUPPORTED_ACTIONS). */
const ROLLBACK_ACTIONS = new Set([
  "update_document",
  "accept_category_suggestion",
  "rollback_document",
  "update_category",
  "activate_category",
  "deactivate_category",
  "rollback_category",
  "edit_ocr",
  "rollback_ocr",
]);

function Preview({ logId, onClose }: { logId: number; onClose: () => void }) {
  const client = useQueryClient();
  const plan = useQuery({
    queryKey: ["rollback", logId],
    queryFn: () => api<Rollback>(`/api/audit/${logId}/rollback`),
  });
  const run = useMutation({
    mutationFn: (confirm: boolean) =>
      api<Rollback>(`/api/audit/${logId}/rollback`, { method: "POST", json: { confirm } }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["audit"] });
      client.invalidateQueries({ queryKey: ["documents"] });
      client.invalidateQueries({ queryKey: ["categories"] });
      onClose();
    },
  });
  const stale = run.error instanceof ApiError && run.error.code === "ROLLBACK_STALE";
  const changed = plan.data?.changed_since || stale;

  return (
    <Modal
      title="Khôi phục thay đổi"
      onClose={onClose}
      actions={
        plan.data?.supported && (
          <button className="btn btn-primary" disabled={run.isPending} onClick={() => run.mutate(Boolean(changed))}>
            {changed ? "Vẫn khôi phục" : "Khôi phục"}
          </button>
        )
      }
    >
      {plan.isPending ? (
        <Loading />
      ) : plan.error ? (
        <ErrorBox error={plan.error} />
      ) : !plan.data?.supported ? (
        <p>Dòng nhật ký này không hỗ trợ khôi phục.</p>
      ) : (
        <div className="stack">
          <p>Khôi phục tạo một thay đổi mới, không xóa lịch sử.</p>
          {changed && (
            <p style={{ color: "var(--c-warn)" }}>
              Dữ liệu đã được sửa tiếp sau thay đổi này. Khôi phục sẽ ghi đè các thay đổi sau đó.
            </p>
          )}
          <div className="row" style={{ alignItems: "flex-start" }}>
            <div className="grow">
              <strong>Hiện tại</strong>
              <pre style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(plan.data.current, null, 2)}</pre>
            </div>
            <div className="grow">
              <strong>Sau khi khôi phục</strong>
              <pre style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(plan.data.target, null, 2)}</pre>
            </div>
          </div>
          {!stale && <ErrorBox error={run.error} />}
        </div>
      )}
    </Modal>
  );
}

export function RollbackButton({ log }: AuditRowProps) {
  const [open, setOpen] = useState(false);
  if (log.result !== "success" || !ROLLBACK_ACTIONS.has(log.action)) return null;
  return (
    <>
      <button className="btn btn-sm" onClick={() => setOpen(true)}>
        Khôi phục
      </button>
      {open && <Preview logId={log.id} onClose={() => setOpen(false)} />}
    </>
  );
}
