import { useRef, useState, type FormEvent } from "react";
import { Link } from "react-router";

import { JobStatus } from "@/features/jobs";
import type { UploadOut } from "@/shared/api/types";
import { ErrorBox, Field, PageHeader, fieldErrors } from "@/shared/components/ui";
import { useCategories } from "@/shared/hooks/useCategories";
import { formatBytes } from "@/shared/lib/format";
import { SlotList, useSlots } from "@/shared/slots";

import { useUpload } from "./api";
import s from "./documents.module.css";

const ACCEPT = ".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg";
const MAX_MB = Number(import.meta.env.VITE_MAX_UPLOAD_MB ?? 25);

/** UC-01 (FR-03): FormData; server xác minh nội dung file và giới hạn; lỗi 400/413/415/422 hiển thị rõ. */
export function UploadPage() {
  const categories = useCategories(true);
  const upload = useUpload();
  const { uploadFields } = useSlots();
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<UploadOut | null>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const errors = fieldErrors(upload.error);
  const tooBig = file !== null && file.size > MAX_MB * 1024 * 1024;

  const submit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    upload.mutate(form, {
      onSuccess: (data) => {
        setResult(data);
        formRef.current?.reset();
        setFile(null);
      },
    });
  };

  return (
    <div className={s.upload}>
      <PageHeader title="Tải tài liệu lên" subtitle="PDF, PNG hoặc JPG. Sau khi tải lên, hệ thống tự xếp hàng OCR." />
      {result && (
        <div className="card stack" style={{ marginBottom: 16 }}>
          <strong>Đã tải lên thành công.</strong>
          <JobStatus jobId={result.job_id} />
          <div className="row">
            <Link className="btn btn-primary" to={`/documents/${result.document_id}`}>
              Mở tài liệu
            </Link>
            <button className="btn" onClick={() => setResult(null)}>
              Tải tài liệu khác
            </button>
          </div>
        </div>
      )}
      <form ref={formRef} className="card stack" onSubmit={submit}>
        <ErrorBox error={upload.error} />
        <Field label="File" htmlFor="file" error={errors.file} hint={`Tối đa ${MAX_MB} MB`}>
          <div className={s.drop}>
            <input
              id="file"
              name="file"
              type="file"
              accept={ACCEPT}
              required
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
            {file && (
              <div className="muted">
                {file.name} · {formatBytes(file.size)}
                {tooBig && <span style={{ color: "var(--c-danger)" }}> — vượt quá giới hạn</span>}
              </div>
            )}
          </div>
        </Field>
        <Field label="Tiêu đề" htmlFor="title" hint="Để trống sẽ dùng tên file" error={errors.title}>
          <input id="title" name="title" className="input" maxLength={255} />
        </Field>
        <Field label="Danh mục" htmlFor="category_id" error={errors.category_id}>
          <select id="category_id" name="category_id" className="select" required defaultValue="">
            <option value="" disabled>
              — Chọn danh mục —
            </option>
            {categories.data?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </Field>
        <SlotList items={uploadFields} props={{}} />
        <div className="row">
          <button className="btn btn-primary" type="submit" disabled={upload.isPending || tooBig}>
            {upload.isPending ? "Đang tải lên..." : "Tải lên"}
          </button>
          <Link className="btn" to="/documents">
            Hủy
          </Link>
        </div>
      </form>
    </div>
  );
}
