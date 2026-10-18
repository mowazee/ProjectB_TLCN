import { Download, PencilLine, Trash2 } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router";

import { JobStatus } from "@/features/jobs";
import type { DocumentOut } from "@/shared/api/types";
import {
  ApprovalBadge,
  EmptyState,
  ErrorBox,
  Field,
  Loading,
  Modal,
  PageHeader,
  PageStatusBadge,
  Tabs,
  fieldErrors,
  type TabDef,
} from "@/shared/components/ui";
import { useCategories } from "@/shared/hooks/useCategories";
import { formatBytes, formatDateTime } from "@/shared/lib/format";
import { SlotList, useSlots } from "@/shared/slots";

import {
  documentKeys,
  fileUrl,
  pageImageUrl,
  useDeleteDocument,
  useDocument,
  usePages,
  useUpdateDocument,
} from "./api";
import { BackToList } from "./BackToList";
import s from "./documents.module.css";

function EditMetadata({ doc, onClose }: { doc: DocumentOut; onClose: () => void }) {
  const categories = useCategories(true);
  const update = useUpdateDocument(doc.id);
  const errors = fieldErrors(update.error);
  const [title, setTitle] = useState(doc.title);
  const [categoryId, setCategoryId] = useState(String(doc.category.id));
  const [code, setCode] = useState(doc.document_code ?? "");

  const submit = (e: FormEvent) => {
    e.preventDefault();
    update.mutate(
      { title: title.trim(), category_id: Number(categoryId), document_code: code.trim() || null },
      { onSuccess: onClose },
    );
  };
  const currentInactive = categories.data && !categories.data.some((c) => c.id === doc.category.id);
  return (
    <Modal
      title="Sửa thông tin tài liệu"
      onClose={onClose}
      actions={
        <button className="btn btn-primary" form="edit-doc" type="submit" disabled={update.isPending}>
          Lưu
        </button>
      }
    >
      <form id="edit-doc" className="stack" onSubmit={submit}>
        <ErrorBox error={update.error} />
        <Field label="Tiêu đề" htmlFor="t" error={errors.title}>
          <input
            id="t"
            className="input"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
            maxLength={255}
          />
        </Field>
        <Field label="Danh mục" htmlFor="c" error={errors.category_id}>
          <select id="c" className="select" value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
            {currentInactive && <option value={doc.category.id}>{doc.category.name} (ngừng dùng)</option>}
            {categories.data?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Số hiệu" htmlFor="code" error={errors.document_code}>
          <input id="code" className="input" value={code} onChange={(e) => setCode(e.target.value)} maxLength={100} />
        </Field>
      </form>
    </Modal>
  );
}

function PagesGrid({ doc }: { doc: DocumentOut }) {
  const pages = usePages(doc.id);
  if (pages.isPending) return <Loading />;
  if (pages.error) return <ErrorBox error={pages.error} />;
  if (!pages.data?.length) return <EmptyState>Chưa có trang nào (đang chờ OCR).</EmptyState>;
  return (
    <div className={s.pages}>
      {pages.data.map((p) => (
        <Link key={p.page_number} className={s.thumb} to={`/documents/${doc.id}/pages/${p.page_number}`}>
          <img src={pageImageUrl(doc.id, p.page_number)} alt={`Trang ${p.page_number}`} loading="lazy" />
          <div className="row">
            <strong>Trang {p.page_number}</strong>
            <PageStatusBadge status={p.ocr_status} />
          </div>
        </Link>
      ))}
    </div>
  );
}

export function DocumentDetailPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const client = useQueryClient();
  const doc = useDocument(id);
  const del = useDeleteDocument();
  const { documentTabs, documentActions } = useSlots();
  const [editing, setEditing] = useState(false);

  if (doc.isPending) return <Loading />;
  if (doc.error || !doc.data) {
    return (
      <div className="stack">
        <BackToList />
        <ErrorBox error={doc.error} />
      </div>
    );
  }
  const d = doc.data;

  const remove = () => {
    if (window.confirm(`Chuyển "${d.title}" vào thùng rác?`)) {
      del.mutate(d.id, { onSuccess: () => navigate("/documents") });
    }
  };
  const refresh = () => {
    client.invalidateQueries({ queryKey: documentKeys.detail(d.id) });
    client.invalidateQueries({ queryKey: documentKeys.pages(d.id) });
  };

  const tabs: TabDef[] = [
    { id: "pages", label: `Trang (${d.total_pages})`, render: () => <PagesGrid doc={d} /> },
    ...documentTabs.map((t) => ({
      id: t.id,
      label: t.label,
      render: () => <SlotList items={[t.element]} props={{ document: d }} />,
    })),
  ];

  return (
    <div className="stack">
      <BackToList />
      <PageHeader
        title={d.title}
        subtitle={
          <>
            {d.category.name} · {d.file_type} · {formatBytes(d.bytes)} · tải lên bởi {d.owner?.full_name ?? "—"} lúc{" "}
            {formatDateTime(d.created_at)}
          </>
        }
        actions={
          <div className={s.actions}>
            <SlotList items={documentActions} props={{ document: d }} />
            {/* D-08: ai xem được tài liệu thì tải được file gốc (server ghi nhật ký mỗi lượt tải) */}
            <a className="btn" href={fileUrl(d.id)}>
              <Download size={16} aria-hidden /> Tải file gốc
            </a>
            {d.can_edit && (
              <>
                <button className="btn" onClick={() => setEditing(true)}>
                  <PencilLine size={16} aria-hidden /> Sửa thông tin
                </button>
                <button className="btn btn-danger" onClick={remove} disabled={del.isPending}>
                  <Trash2 size={16} aria-hidden /> Xóa
                </button>
              </>
            )}
          </div>
        }
      />
      <ErrorBox error={del.error} />
      <div className="card">
        <dl className={s.meta}>
          <div>
            <dt>Số hiệu</dt>
            <dd>{d.document_code ?? "—"}</dd>
          </div>
          <div>
            <dt>Trạng thái duyệt</dt>
            <dd>
              <ApprovalBadge status={d.approval_status} />
            </dd>
          </div>
          <div>
            <dt>Số trang</dt>
            <dd>
              {d.total_pages}
              {d.needs_review_pages > 0 && ` (${d.needs_review_pages} cần xem lại)`}
            </dd>
          </div>
          <div>
            <dt>Cập nhật</dt>
            <dd>{formatDateTime(d.updated_at)}</dd>
          </div>
        </dl>
        {d.job_id && (
          <div style={{ marginTop: 12 }}>
            <JobStatus jobId={d.job_id} canRetry={d.can_edit} onDone={refresh} />
          </div>
        )}
      </div>
      <div className="card">
        <Tabs tabs={tabs} />
      </div>
      {editing && <EditMetadata doc={d} onClose={() => setEditing(false)} />}
    </div>
  );
}
