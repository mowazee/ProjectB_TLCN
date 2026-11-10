import { useState } from "react";

import type { DocumentOut } from "@/shared/api/types";
import { ErrorBox, Field, Modal } from "@/shared/components/ui";
import { ValidityPicker, validityIncomplete, type ValidityValue } from "@/shared/components/validity";
import { validityReasonRequired } from "@/shared/lib/validity";
import { useSession } from "@/shared/session";

import { useUpdateValidity } from "./api";

/** FR-19 (D-14): đổi hiệu lực - chủ sở hữu khi Nháp/Bị từ chối; Kiểm duyệt viên/Admin mọi trạng thái, đã duyệt/xuất bản
 *  bắt buộc lý do (5-500 ký tự). Server vẫn kiểm quyền và lý do. */
export function ValidityDialog({ doc, onClose }: { doc: DocumentOut; onClose: () => void }) {
  const { hasFeature } = useSession();
  const update = useUpdateValidity(doc.id);
  const [value, setValue] = useState<ValidityValue>({
    status: doc.validity_status,
    validUntil: doc.valid_until ?? "",
  });
  const [reason, setReason] = useState("");
  const needReason = validityReasonRequired(doc.approval_status, hasFeature("workflow"));
  const invalid = validityIncomplete(value) || (needReason && reason.trim().length < 5);

  const save = () =>
    update.mutate(
      {
        validity_status: value.status ?? "unspecified",
        valid_until: value.status === "effective_until" ? value.validUntil : null,
        reason: reason.trim() || undefined,
      },
      { onSuccess: onClose },
    );

  return (
    <Modal
      title={`Đổi hiệu lực: ${doc.title}`}
      onClose={onClose}
      actions={
        <button className="btn btn-primary" onClick={save} disabled={update.isPending || invalid}>
          Lưu
        </button>
      }
    >
      <ErrorBox error={update.error} />
      <ValidityPicker value={value} onChange={setValue} />
      <Field label={needReason ? "Lý do thay đổi (bắt buộc, tối thiểu 5 ký tự)" : "Lý do thay đổi"} htmlFor="vr">
        <textarea
          id="vr"
          className="textarea"
          rows={3}
          maxLength={500}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
      </Field>
    </Modal>
  );
}
