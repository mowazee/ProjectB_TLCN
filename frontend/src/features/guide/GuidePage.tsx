import { BookOpen, Download, Pencil, Search, Trash2, Upload } from "lucide-react";
import { useState, type FormEvent } from "react";

import type { Guide } from "@/shared/api/types";
import { EmptyState, ErrorBox, Field, Loading, Modal, PageHeader, Pagination } from "@/shared/components/ui";
import { useDebounce } from "@/shared/hooks/useDebounce";
import { formatBytes, formatDateTime } from "@/shared/lib/format";
import { useSession } from "@/shared/session";

import { guideFileUrl, useDeleteGuide, useGuides, useUpdateGuide, useUploadGuide } from "./api";
import s from "./guide.module.css";

const ACCEPT = ".pdf,.docx,.xlsx,.pptx,.png,.jpg,.jpeg,.mp4";

function UploadDialog({ onClose }: { onClose: () => void }) {
  const upload = useUploadGuide();
  const submit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    upload.mutate(new FormData(e.currentTarget), { onSuccess: onClose });
  };
  return (
    <Modal
      title="Tải lên tài liệu hướng dẫn"
      onClose={onClose}
      actions={
        <button className="btn btn-primary" form="guide-upload" type="submit" disabled={upload.isPending}>
          {upload.isPending ? "Đang tải lên..." : "Tải lên"}
        </button>
      }
    >
      <form id="guide-upload" className="stack" onSubmit={submit}>
        <ErrorBox error={upload.error} />
        <Field label="File (PDF, Word, Excel, PowerPoint, ảnh, video MP4)" htmlFor="gf">
          <input id="gf" name="file" type="file" accept={ACCEPT} required />
        </Field>
        <Field label="Tiêu đề (để trống = tên file)" htmlFor="gt">
          <input id="gt" name="title" className="input" maxLength={255} />
        </Field>
        <Field label="Mô tả" htmlFor="gd">
          <textarea id="gd" name="description" className="textarea" rows={3} maxLength={2000} />
        </Field>
      </form>
    </Modal>
  );
}

function EditDialog({ guide, onClose }: { guide: Guide; onClose: () => void }) {
  const update = useUpdateGuide(guide.id);
  const [title, setTitle] = useState(guide.title);
  const [description, setDescription] = useState(guide.description ?? "");
  const submit = (e: FormEvent) => {
    e.preventDefault();
    update.mutate({ title: title.trim(), description: description.trim() || null }, { onSuccess: onClose });
  };
  return (
    <Modal
      title="Sửa tài liệu hướng dẫn"
      onClose={onClose}
      actions={
        <button className="btn btn-primary" form="guide-edit" type="submit" disabled={update.isPending}>
          Lưu
        </button>
      }
    >
      <form id="guide-edit" className="stack" onSubmit={submit}>
        <ErrorBox error={update.error} />
        <Field label="Tiêu đề" htmlFor="et">
          <input
            id="et"
            className="input"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
            maxLength={255}
          />
        </Field>
        <Field label="Mô tả" htmlFor="ed">
          <textarea
            id="ed"
            className="textarea"
            rows={3}
            maxLength={2000}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </Field>
      </form>
    </Modal>
  );
}

/** FR-21 (v0.16): Hướng dẫn sử dụng - mọi người dùng tìm và mở tài liệu hướng dẫn; Admin tải lên, sửa, xóa. */
export function GuidePage() {
  const { hasRole } = useSession();
  const isAdmin = hasRole("ADMIN");
  const [input, setInput] = useState("");
  const q = useDebounce(input.trim());
  const [page, setPage] = useState(1);
  const guides = useGuides(q, page);
  const remove = useDeleteGuide();
  const [uploading, setUploading] = useState(false);
  const [editing, setEditing] = useState<Guide | null>(null);
  const items = guides.data?.items ?? [];

  const confirmDelete = (g: Guide) => {
    if (window.confirm(`Xóa tài liệu hướng dẫn "${g.title}"?`)) remove.mutate(g.id);
  };

  return (
    <div className="stack">
      <PageHeader icon={BookOpen} title="Hướng dẫn sử dụng" subtitle="Tài liệu hướng dẫn sử dụng hệ thống." />
      <div className={s.panel}>
        <div className={s.toolbar}>
          <label className={s.search}>
            <Search size={20} aria-hidden />
            <input
              type="search"
              placeholder="Tìm kiếm tài liệu hướng dẫn"
              aria-label="Tìm kiếm tài liệu hướng dẫn"
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                setPage(1);
              }}
            />
          </label>
          {isAdmin && (
            <button className="btn btn-primary" onClick={() => setUploading(true)}>
              <Upload size={16} aria-hidden /> Tải lên tài liệu
            </button>
          )}
        </div>
        <ErrorBox error={guides.error ?? remove.error} />
        {guides.isPending ? (
          <Loading />
        ) : !items.length ? (
          <EmptyState icon={BookOpen}>
            {q ? `Không tìm thấy tài liệu cho “${q}”.` : "Chưa có tài liệu hướng dẫn."}
          </EmptyState>
        ) : (
          <>
            <div className={s.tableWrap}>
              <table className={s.table}>
                <thead>
                  <tr>
                    <th>Tiêu đề</th>
                    <th>Người đăng</th>
                    <th>Thời gian đăng</th>
                    {isAdmin && <th aria-label="Thao tác" />}
                  </tr>
                </thead>
                <tbody>
                  {items.map((g) => (
                    <tr key={g.id}>
                      <td>
                        <a
                          className={s.titleLink}
                          href={guideFileUrl(g.id)}
                          target={g.inline ? "_blank" : undefined}
                          rel="noreferrer"
                          download={g.inline ? undefined : g.file_name}
                        >
                          {g.title}
                        </a>
                        <span className={s.meta}>
                          {g.inline ? "" : <Download size={12} aria-hidden />} {g.file_name} · {formatBytes(g.bytes)}
                        </span>
                        {g.description && <div className={s.desc}>{g.description}</div>}
                      </td>
                      <td>{g.uploaded_by ?? "—"}</td>
                      <td className={s.nowrap}>{formatDateTime(g.created_at)}</td>
                      {isAdmin && (
                        <td>
                          <div className={s.actions}>
                            <button className="btn btn-sm" aria-label={`Sửa ${g.title}`} onClick={() => setEditing(g)}>
                              <Pencil size={14} aria-hidden />
                            </button>
                            <button
                              className="btn btn-sm btn-danger"
                              aria-label={`Xóa ${g.title}`}
                              onClick={() => confirmDelete(g)}
                              disabled={remove.isPending}
                            >
                              <Trash2 size={14} aria-hidden />
                            </button>
                          </div>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination
              page={page}
              pageSize={guides.data?.page_size ?? 20}
              total={guides.data?.total ?? 0}
              onChange={setPage}
            />
          </>
        )}
      </div>
      {uploading && <UploadDialog onClose={() => setUploading(false)} />}
      {editing && <EditDialog guide={editing} onClose={() => setEditing(null)} />}
    </div>
  );
}
