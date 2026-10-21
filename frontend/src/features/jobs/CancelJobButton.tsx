import { CircleStop } from "lucide-react";
import { useState } from "react";

import { ErrorBox, Modal } from "@/shared/components/ui";

import { useCancelJob } from "./useJob";

/** Nút Dừng kèm hộp thoại xác nhận (FR-04 v0.10). Chỉ render khi job đang chờ/đang xử lý và người dùng có quyền. */
export function CancelJobButton({ jobId, processing }: { jobId: string; processing: boolean }) {
  const cancel = useCancelJob();
  const [confirming, setConfirming] = useState(false);
  return (
    <>
      <button className="btn btn-sm" onClick={() => setConfirming(true)} disabled={cancel.isPending}>
        <CircleStop size={14} aria-hidden /> Dừng
      </button>
      {confirming && (
        <Modal
          title="Dừng xử lý tài liệu?"
          onClose={() => setConfirming(false)}
          closeLabel="Không"
          actions={
            <button
              className="btn btn-danger"
              disabled={cancel.isPending}
              onClick={() => cancel.mutate(jobId, { onSuccess: () => setConfirming(false) })}
            >
              <CircleStop size={16} aria-hidden /> Dừng xử lý
            </button>
          }
        >
          <div className="stack" style={{ gap: 10 }}>
            <ErrorBox error={cancel.error} />
            <p style={{ margin: 0 }}>
              {processing
                ? "Hệ thống sẽ dừng sau trang đang xử lý (OCR một trang có thể mất vài chục giây)."
                : "Job chưa bắt đầu sẽ được hủy ngay."}{" "}
              Các trang đã xử lý được giữ lại; bạn có thể bấm <strong>Chạy lại</strong> để xử lý lại từ đầu.
            </p>
          </div>
        </Modal>
      )}
    </>
  );
}
