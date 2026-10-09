import { useState, type ReactNode } from "react";
import { Link, useParams, useSearchParams } from "react-router";

import { EmptyState, ErrorBox, Loading, PageHeader, PageStatusBadge } from "@/shared/components/ui";
import { formatConfidence, formatDateTime } from "@/shared/lib/format";

import { usePageDetail } from "./api";
import s from "./ocr.module.css";
import { PageImage } from "./PageImage";

function PageLink({ to, children }: { to: string | null; children: ReactNode }) {
  return to ? (
    <Link className="btn" to={to}>
      {children}
    </Link>
  ) : (
    <button className="btn" disabled>
      {children}
    </button>
  );
}

/** UC-05a Xem/Preview: ảnh trang cạnh text hiệu lực; text hiển thị như text, không chèn HTML (SDD mục 14). */
export function PageViewerPage() {
  const { id = "", page = "1" } = useParams();
  const [params] = useSearchParams();
  const query = params.get("q") ?? "";
  const pageNumber = Number(page);
  const detail = usePageDetail(id, pageNumber);
  const [showRaw, setShowRaw] = useState(false);

  if (detail.isPending) return <Loading />;
  if (detail.error || !detail.data) return <ErrorBox error={detail.error} />;
  const p = detail.data;
  const qs = query ? `?q=${encodeURIComponent(query)}` : "";

  return (
    <div className="stack">
      <PageHeader
        title={`Trang ${p.page_number}/${p.total_pages}`}
        subtitle={<Link to={`/documents/${id}`}>‹ Về tài liệu</Link>}
        actions={
          <>
            <PageLink to={pageNumber > 1 ? `/documents/${id}/pages/${pageNumber - 1}${qs}` : null}>
              ‹ Trang trước
            </PageLink>
            <PageLink to={pageNumber < p.total_pages ? `/documents/${id}/pages/${pageNumber + 1}${qs}` : null}>
              Trang sau ›
            </PageLink>
            {p.can_edit && (
              <Link className="btn btn-primary" to={`/documents/${id}/pages/${pageNumber}/edit`}>
                Sửa OCR
              </Link>
            )}
          </>
        }
      />
      <div className={s.split}>
        {p.width > 0 ? (
          <PageImage documentId={id} pageNumber={pageNumber} width={p.width} height={p.height} query={query} />
        ) : (
          <EmptyState>Trang chưa có ảnh (OCR lỗi hoặc chưa xử lý).</EmptyState>
        )}
        <div className={`card ${s.sticky}`}>
          <dl className={s.info}>
            <dt>Trạng thái</dt>
            <dd>
              <PageStatusBadge status={p.ocr_status} />
            </dd>
            <dt>Nguồn text</dt>
            <dd>{p.is_text_layer ? "Lớp chữ của PDF (không OCR)" : (p.engine_version ?? "—")}</dd>
            <dt title="Điểm model tự đánh giá, không phải độ chính xác">Điểm tin cậy</dt>
            <dd>{p.is_text_layer ? "—" : formatConfidence(p.confidence)}</dd>
            <dt>Phiên bản</dt>
            <dd>
              {p.version === 0 ? "OCR gốc" : `v${p.version}`}
              {p.edited_at && ` · sửa lúc ${formatDateTime(p.edited_at)}`}
            </dd>
          </dl>
          <div className="row" style={{ marginBottom: 8 }}>
            <label className="row">
              <input type="checkbox" checked={showRaw} onChange={(e) => setShowRaw(e.target.checked)} /> Xem text OCR
              thô
            </label>
          </div>
          <pre className={s.text}>{(showRaw ? p.raw_text : p.effective_text) || "(trống)"}</pre>
        </div>
      </div>
    </div>
  );
}
