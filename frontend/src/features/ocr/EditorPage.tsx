import { ArrowLeft } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";

import { ApiError } from "@/shared/api/client";
import type { PageDetail } from "@/shared/api/types";
import { ErrorBox, Loading, PageHeader } from "@/shared/components/ui";
import { formatDateTime } from "@/shared/lib/format";
import { SlotList, useSlots } from "@/shared/slots";

import { fetchPage, pageKey, usePageDetail, useSaveCorrection } from "./api";
import s from "./ocr.module.css";
import { PageImage } from "./PageImage";

/**
 * UC-03 OCR Editor (FR-05): draft nằm trong state; lưu gửi corrected_text + base_version.
 * 409 VERSION_CONFLICT: GIỮ NGUYÊN draft, cho tải bản mới nhất của server để so sánh rồi quyết định.
 */
export function EditorForm({ documentId, page }: { documentId: string; page: PageDetail }) {
  const navigate = useNavigate();
  const client = useQueryClient();
  const save = useSaveCorrection(documentId, page.page_number);
  const { editorTools } = useSlots();
  const [draft, setDraft] = useState(page.effective_text);
  const [baseVersion, setBaseVersion] = useState(page.version);
  const [server, setServer] = useState<PageDetail | null>(null);
  const dirty = draft !== page.effective_text || baseVersion !== page.version;
  const conflict = save.error instanceof ApiError && save.error.code === "VERSION_CONFLICT";

  useEffect(() => {
    if (!dirty) return;
    const warn = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  const submit = () =>
    save.mutate(
      { corrected_text: draft, base_version: baseVersion },
      { onSuccess: () => navigate(`/documents/${documentId}/pages/${page.page_number}`) },
    );

  const loadLatest = async () => {
    const latest = await fetchPage(documentId, page.page_number);
    client.setQueryData(pageKey(documentId, page.page_number), latest);
    setServer(latest);
  };

  return (
    <div className="stack">
      {conflict && (
        <div className={s.conflict} role="alert">
          <strong>Trang đã được người khác cập nhật</strong> (phiên bản hiện tại v
          {String(save.error instanceof ApiError ? (save.error.details?.current_version ?? "?") : "?")}). Bản nháp của
          bạn vẫn được giữ nguyên bên dưới.
          <div className="row" style={{ marginTop: 8 }}>
            <button className="btn btn-sm" onClick={loadLatest}>
              Tải bản mới nhất để so sánh
            </button>
          </div>
          {server && (
            <div className="stack" style={{ marginTop: 8 }}>
              <span className="muted">
                Bản mới nhất v{server.version}
                {server.edited_at && ` (${formatDateTime(server.edited_at)})`}:
              </span>
              <pre className={s.text} style={{ maxHeight: 200 }}>
                {server.effective_text}
              </pre>
              <div className="row">
                <button
                  className="btn btn-sm"
                  onClick={() => {
                    setBaseVersion(server.version);
                    save.reset();
                  }}
                >
                  Giữ bản nháp của tôi và lưu đè lên v{server.version}
                </button>
                <button
                  className="btn btn-sm"
                  onClick={() => {
                    setDraft(server.effective_text);
                    setBaseVersion(server.version);
                    save.reset();
                  }}
                >
                  Bỏ nháp, dùng bản mới nhất
                </button>
              </div>
            </div>
          )}
        </div>
      )}
      {!conflict && <ErrorBox error={save.error} />}
      <textarea
        className={`textarea ${s.editor}`}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        aria-label="Nội dung OCR"
        spellCheck={false}
      />
      <div className="row">
        <button className="btn btn-primary" onClick={submit} disabled={save.isPending || conflict}>
          {save.isPending ? "Đang lưu..." : "Lưu phiên bản mới"}
        </button>
        <Link className="btn" to={`/documents/${documentId}/pages/${page.page_number}`}>
          Hủy
        </Link>
        <span className="muted">
          Sửa trên v{baseVersion}
          {dirty ? " · có thay đổi chưa lưu" : ""}
        </span>
      </div>
      <SlotList
        items={editorTools}
        props={{ documentId, pageNumber: page.page_number, currentVersion: page.version }}
      />
    </div>
  );
}

export function EditorPage() {
  const { id = "", page = "1" } = useParams();
  const detail = usePageDetail(id, Number(page));
  if (detail.isPending) return <Loading />;
  if (detail.error || !detail.data) return <ErrorBox error={detail.error} />;
  const p = detail.data;
  return (
    <div className="stack">
      <PageHeader
        title={`Sửa OCR - trang ${p.page_number}/${p.total_pages}`}
        subtitle={
          <Link to={`/documents/${id}/pages/${p.page_number}`}>
            <ArrowLeft size={14} aria-hidden /> Về xem trang
          </Link>
        }
      />
      {!p.can_edit ? (
        <ErrorBox error={new Error("Bạn không có quyền sửa tài liệu này")} />
      ) : (
        <div className={s.split}>
          {p.width > 0 && (
            <PageImage documentId={id} pageNumber={p.page_number} width={p.width} height={p.height} query="" />
          )}
          <EditorForm key={`${p.page_number}`} documentId={id} page={p} />
        </div>
      )}
    </div>
  );
}
