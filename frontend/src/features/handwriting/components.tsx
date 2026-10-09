import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "@/shared/api/client";
import type { ReprocessOut } from "@/shared/api/types";
import { ErrorBox, Field, Modal } from "@/shared/components/ui";
import type { DocumentSlotProps } from "@/shared/types/feature";

/** Trường thêm vào form upload: is_handwritten -> OCR bằng HandwritingEngine trên hàng đợi ocr_hw. */
export function HandwrittenField() {
  return (
    <label className="row">
      <input type="checkbox" name="is_handwritten" value="true" />
      Tài liệu viết tay (OCR chữ viết tay thử nghiệm)
    </label>
  );
}

/** P2-03: chạy lại OCR với profile in/chữ viết tay; 409 khi đang có job chạy. */
export function ReprocessButton({ document }: DocumentSlotProps) {
  const client = useQueryClient();
  const [open, setOpen] = useState(false);
  const [profile, setProfile] = useState(document.is_handwritten ? "handwriting" : "print");
  const run = useMutation({
    mutationFn: () =>
      api<ReprocessOut>(`/api/documents/${document.id}/reprocess`, { method: "POST", json: { ocr_profile: profile } }),
    onSuccess: () => {
      setOpen(false);
      client.invalidateQueries({ queryKey: ["documents"] });
    },
  });
  if (!document.can_edit) return null;
  return (
    <>
      <button className="btn" onClick={() => setOpen(true)}>
        Chạy lại OCR
      </button>
      {open && (
        <Modal
          title="Chạy lại OCR"
          onClose={() => setOpen(false)}
          actions={
            <button className="btn btn-primary" onClick={() => run.mutate()} disabled={run.isPending}>
              Chạy
            </button>
          }
        >
          <ErrorBox error={run.error} />
          <Field label="Cấu hình OCR" htmlFor="profile" hint="Bản sửa của người dùng vẫn là nội dung hiệu lực.">
            <select id="profile" className="select" value={profile} onChange={(e) => setProfile(e.target.value)}>
              <option value="print">Chữ in</option>
              <option value="handwriting">Chữ viết tay (thử nghiệm)</option>
            </select>
          </Field>
        </Modal>
      )}
    </>
  );
}
