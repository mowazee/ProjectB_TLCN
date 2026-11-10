import { ArrowDown, ArrowUp, Upload, X } from "lucide-react";
import { useRef, useState, type FormEvent } from "react";
import { Link } from "react-router";

import { JobStatus } from "@/features/jobs";
import type { UploadOut } from "@/shared/api/types";
import { CategoryModePicker, type CategoryMode } from "@/shared/components/CategoryModePicker";
import { ErrorBox, Field, PageHeader, fieldErrors } from "@/shared/components/ui";
import { useCategories } from "@/shared/hooks/useCategories";
import { formatBytes } from "@/shared/lib/format";
import { useSession } from "@/shared/session";
import { SlotList, useSlots } from "@/shared/slots";

import { useUpload } from "./api";
import s from "./documents.module.css";

const ACCEPT = ".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg";
const MAX_MB = Number(import.meta.env.VITE_MAX_UPLOAD_MB ?? 25);

const MAX_MERGE = Number(import.meta.env.VITE_MAX_MERGE_FILES ?? 20);

/** UC-01 (FR-03): FormData; server xác minh nội dung file và giới hạn; lỗi 400/413/415/422 hiển thị rõ.
 *  FR-16 (v0.13): chọn nhiều ảnh/PDF, sắp thứ tự → gửi files[] để server gộp thành một PDF, một tài liệu. */
export function UploadPage() {
  const categories = useCategories(true, { selectable: true });
  const { hasFeature } = useSession();
  const canAuto = hasFeature("classification"); // Danh mục gợi ý cần P2-05
  const [mode, setMode] = useState<CategoryMode>("auto");
  const categoryMode: CategoryMode = canAuto ? mode : "user";
  const upload = useUpload();
  const { uploadFields } = useSlots();
  const [files, setFiles] = useState<File[]>([]);
  const [result, setResult] = useState<(UploadOut & { auto: boolean }) | null>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const errors = fieldErrors(upload.error);
  const totalBytes = files.reduce((n, f) => n + f.size, 0);
  const tooBig = totalBytes > MAX_MB * 1024 * 1024;
  const tooMany = files.length > MAX_MERGE;
  const move = (i: number, d: -1 | 1) =>
    setFiles((list) => {
      const next = [...list];
      [next[i], next[i + d]] = [next[i + d], next[i]];
      return next;
    });

  const submit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    form.set("category_mode", categoryMode);
    form.delete("file");
    if (files.length > 1) files.forEach((f) => form.append("files", f));
    else if (files.length === 1) form.set("file", files[0]);
    upload.mutate(form, {
      onSuccess: (data) => {
        setResult({ ...data, auto: categoryMode === "auto" });
        formRef.current?.reset();
        setFiles([]);
      },
    });
  };

  return (
    <div className={s.upload}>
      <PageHeader
        icon={Upload}
        title="Tải tài liệu lên"
        subtitle="PDF, PNG hoặc JPG. Sau khi tải lên, hệ thống tự xếp hàng OCR."
      />
      {result && (
        <div className="card stack" style={{ marginBottom: 16 }}>
          <strong>Đã tải lên thành công.</strong>
          {result.auto && (
            <span className="muted">Danh mục sẽ được tự chọn sau khi OCR xong — xem ở tab Gợi ý danh mục.</span>
          )}
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
        <Field
          label="File"
          htmlFor="file"
          error={errors.file ?? errors.files}
          hint={`Tối đa ${MAX_MB} MB. Chọn nhiều ảnh/PDF (tối đa ${MAX_MERGE}) để gộp thành một tài liệu theo thứ tự bên dưới.`}
        >
          <div className={s.drop}>
            <input
              id="file"
              name="file"
              type="file"
              accept={ACCEPT}
              multiple
              required={files.length === 0}
              onChange={(e) => {
                const picked = Array.from(e.target.files ?? []);
                if (picked.length) setFiles((list) => [...list, ...picked]);
                e.target.value = "";
              }}
            />
            {files.length === 1 && (
              <div className="muted">
                {files[0].name} · {formatBytes(files[0].size)}
                {tooBig && <span style={{ color: "var(--c-danger)" }}> — vượt quá giới hạn</span>}
              </div>
            )}
            {files.length > 1 && (
              <div className="stack">
                <span className="muted">
                  Gộp {files.length} file thành một tài liệu PDF ({formatBytes(totalBytes)})
                  {tooBig && <span style={{ color: "var(--c-danger)" }}> — tổng dung lượng vượt quá giới hạn</span>}
                  {tooMany && <span style={{ color: "var(--c-danger)" }}> — quá {MAX_MERGE} file</span>}
                </span>
                <ol className={s.mergeList} aria-label="Thứ tự gộp">
                  {files.map((f, i) => (
                    <li key={`${f.name}-${i}`}>
                      <span className="grow">
                        {f.name} · {formatBytes(f.size)}
                      </span>
                      <button
                        type="button"
                        className="btn btn-sm btn-icon"
                        aria-label={`Đưa ${f.name} lên`}
                        disabled={i === 0}
                        onClick={() => move(i, -1)}
                      >
                        <ArrowUp size={14} aria-hidden />
                      </button>
                      <button
                        type="button"
                        className="btn btn-sm btn-icon"
                        aria-label={`Đưa ${f.name} xuống`}
                        disabled={i === files.length - 1}
                        onClick={() => move(i, 1)}
                      >
                        <ArrowDown size={14} aria-hidden />
                      </button>
                      <button
                        type="button"
                        className="btn btn-sm btn-icon"
                        aria-label={`Bỏ ${f.name}`}
                        onClick={() => setFiles((list) => list.filter((_, k) => k !== i))}
                      >
                        <X size={14} aria-hidden />
                      </button>
                    </li>
                  ))}
                </ol>
              </div>
            )}
          </div>
        </Field>
        <Field label="Tiêu đề" htmlFor="title" hint="Để trống sẽ dùng tên file" error={errors.title}>
          <input id="title" name="title" className="input" maxLength={255} />
        </Field>
        {canAuto && (
          <Field label="Danh mục" error={errors.category_mode}>
            <CategoryModePicker value={mode} onChange={setMode} />
          </Field>
        )}
        {categoryMode === "user" && (
          <Field label={canAuto ? "Chọn danh mục" : "Danh mục"} htmlFor="category_id" error={errors.category_id}>
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
        )}
        <SlotList items={uploadFields} props={{}} />
        <div className="row">
          <button className="btn btn-primary" type="submit" disabled={upload.isPending || tooBig || tooMany}>
            <Upload size={16} aria-hidden /> {upload.isPending ? "Đang tải lên..." : "Tải lên"}
          </button>
          <Link className="btn" to="/documents">
            Hủy
          </Link>
        </div>
      </form>
    </div>
  );
}
