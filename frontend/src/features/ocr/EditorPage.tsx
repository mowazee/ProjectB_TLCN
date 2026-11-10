import { ArrowLeft, ChevronLeft, ChevronRight, Redo2, Undo2, ZoomIn, ZoomOut } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { Link, useNavigate, useParams } from "react-router";

import { ApiError } from "@/shared/api/client";
import type { PageDetail } from "@/shared/api/types";
import { ErrorBox, Loading, PageHeader } from "@/shared/components/ui";
import { formatDateTime } from "@/shared/lib/format";
import { SlotList, useSlots } from "@/shared/slots";

import { fetchPage, pageKey, usePageDetail, useSaveCorrection } from "./api";
import {
  History,
  countMatches,
  diffLines,
  findNext,
  isLow,
  lineIndexAt,
  locateBox,
  matchBox,
  replaceAll,
  type LineBox,
} from "./editorUtils";
import s from "./ocr.module.css";
import { PageImage } from "./PageImage";

const draftKey = (documentId: string, page: number, version: number) => `ocr-draft:${documentId}:${page}:${version}`;

function readDraft(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeDraft(key: string, value: string | null) {
  try {
    if (value === null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, value);
  } catch {
    /* trình duyệt chặn lưu trữ: bỏ qua, nháp chỉ là tiện ích */
  }
}

/**
 * UC-03 OCR Editor (FR-05): draft nằm trong state; lưu gửi corrected_text + base_version.
 * 409 VERSION_CONFLICT: GIỮ NGUYÊN draft, cho tải bản mới nhất của server để so sánh rồi quyết định.
 * Mức 1 (SDD v0.13): tô sáng dòng trên ảnh, dòng tin cậy thấp, tìm/thay thế, hoàn tác/làm lại, Ctrl+S,
 * chuyển trang, nháp tự lưu trong trình duyệt, xem khác biệt với bản OCR, xác nhận khi rời trang.
 */
export function EditorForm({
  documentId,
  page,
  onActiveBox,
}: {
  documentId: string;
  page: PageDetail;
  onActiveBox?: (box: number[] | null) => void;
}) {
  const navigate = useNavigate();
  const client = useQueryClient();
  const save = useSaveCorrection(documentId, page.page_number);
  const { editorTools } = useSlots();
  const key = draftKey(documentId, page.page_number, page.version);
  const [restorable, setRestorable] = useState(() => {
    const saved = readDraft(key);
    return saved !== null && saved !== page.effective_text ? saved : null;
  });
  const [draft, setDraftState] = useState(page.effective_text);
  const [baseVersion, setBaseVersion] = useState(page.version);
  const [server, setServer] = useState<PageDetail | null>(null);
  const [find, setFind] = useState("");
  const [replacement, setReplacement] = useState("");
  const [matchCase, setMatchCase] = useState(false);
  const [showDiff, setShowDiff] = useState(false);
  const [lowCursor, setLowCursor] = useState(-1);
  const [history] = useState(() => new History());
  const area = useRef<HTMLTextAreaElement>(null);
  const [, force] = useState(0);
  const boxes = page.boxes as LineBox[];
  const lowIdx = useMemo(() => boxes.flatMap((b, i) => (isLow(b) ? [i] : [])), [boxes]);
  const dirty = draft !== page.effective_text || baseVersion !== page.version;
  const conflict = save.error instanceof ApiError && save.error.code === "VERSION_CONFLICT";

  const setDraft = useCallback(
    (next: string) => {
      setDraftState((prev) => {
        if (prev !== next) history.push(prev);
        return next;
      });
      force((n) => n + 1);
    },
    [history],
  );

  // Nháp tự lưu (chỉ ở trình duyệt, không tạo version)
  useEffect(() => {
    const t = window.setTimeout(() => writeDraft(key, dirty ? draft : null), 500);
    return () => window.clearTimeout(t);
  }, [draft, dirty, key]);

  useEffect(() => {
    if (!dirty) return;
    const warn = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  const select = (range: [number, number] | null) => {
    const el = area.current;
    if (!el || !range) return;
    el.focus();
    el.setSelectionRange(range[0], range[1]);
    syncHighlight();
  };

  const syncHighlight = () => {
    const el = area.current;
    if (!el || !onActiveBox) return;
    const k = matchBox(el.value, lineIndexAt(el.value, el.selectionStart), boxes);
    onActiveBox(k === null ? null : boxes[k].box);
  };

  const submit = () =>
    save.mutate(
      { corrected_text: draft, base_version: baseVersion },
      {
        onSuccess: () => {
          writeDraft(key, null);
          navigate(`/documents/${documentId}/pages/${page.page_number}`);
        },
      },
    );

  const leave = (to: string) => {
    if (dirty && !window.confirm("Có thay đổi chưa lưu. Rời trang? (bản nháp vẫn được giữ trong trình duyệt)")) return;
    navigate(to);
  };

  const undo = () => {
    const prev = history.undo(draft);
    if (prev !== null) {
      setDraftState(prev);
      force((n) => n + 1);
    }
  };
  const redo = () => {
    const next = history.redo(draft);
    if (next !== null) {
      setDraftState(next);
      force((n) => n + 1);
    }
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    const mod = e.ctrlKey || e.metaKey;
    if (!mod) return;
    const k = e.key.toLowerCase();
    if (k === "s") {
      e.preventDefault();
      if (!save.isPending && !conflict) submit();
    } else if (k === "z" && !e.shiftKey) {
      e.preventDefault();
      undo();
    } else if (k === "y" || (k === "z" && e.shiftKey)) {
      e.preventDefault();
      redo();
    } else if (k === "f") {
      e.preventDefault();
      document.getElementById("ocr-find")?.focus();
    }
  };

  const findNextMatch = () => {
    const el = area.current;
    select(findNext(draft, find, el ? el.selectionEnd : 0, matchCase));
  };

  const replaceOne = () => {
    const el = area.current;
    if (!el || !find) return;
    const selected = draft.slice(el.selectionStart, el.selectionEnd);
    const same = matchCase ? selected === find : selected.toLowerCase() === find.toLowerCase();
    if (!same) return findNextMatch();
    const start = el.selectionStart;
    const next = draft.slice(0, start) + replacement + draft.slice(el.selectionEnd);
    setDraft(next);
    window.requestAnimationFrame(() => select(findNext(next, find, start + replacement.length, matchCase)));
  };

  const gotoLow = () => {
    if (!lowIdx.length) return;
    const i = (lowCursor + 1) % lowIdx.length;
    setLowCursor(i);
    const k = lowIdx[i];
    onActiveBox?.(boxes[k].box);
    const range = locateBox(draft, boxes, k);
    if (range) select(range);
  };

  const loadLatest = async () => {
    const latest = await fetchPage(documentId, page.page_number);
    client.setQueryData(pageKey(documentId, page.page_number), latest);
    setServer(latest);
  };

  const matches = countMatches(draft, find, matchCase);
  const base = `/documents/${documentId}/pages`;

  return (
    <div className="stack">
      {restorable !== null && (
        <div className={s.conflict} role="status">
          Có bản nháp chưa lưu của trang này trong trình duyệt.
          <div className="row" style={{ marginTop: 8 }}>
            <button
              className="btn btn-sm"
              onClick={() => {
                setDraft(restorable);
                setRestorable(null);
              }}
            >
              Khôi phục bản nháp
            </button>
            <button
              className="btn btn-sm"
              onClick={() => {
                writeDraft(key, null);
                setRestorable(null);
              }}
            >
              Bỏ bản nháp
            </button>
          </div>
        </div>
      )}
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

      <div className={s.toolbar} role="toolbar" aria-label="Công cụ sửa OCR">
        <button
          className="btn btn-sm btn-icon"
          onClick={undo}
          disabled={!history.canUndo}
          aria-label="Hoàn tác (Ctrl+Z)"
          title="Hoàn tác (Ctrl+Z)"
        >
          <Undo2 size={16} aria-hidden />
        </button>
        <button
          className="btn btn-sm btn-icon"
          onClick={redo}
          disabled={!history.canRedo}
          aria-label="Làm lại (Ctrl+Y)"
          title="Làm lại (Ctrl+Y)"
        >
          <Redo2 size={16} aria-hidden />
        </button>
        <input
          id="ocr-find"
          className="input"
          placeholder="Tìm (Ctrl+F)"
          aria-label="Tìm"
          value={find}
          onChange={(e) => setFind(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), findNextMatch())}
        />
        <input
          className="input"
          placeholder="Thay bằng"
          aria-label="Thay bằng"
          value={replacement}
          onChange={(e) => setReplacement(e.target.value)}
        />
        <label className="row muted" style={{ gap: 4 }}>
          <input type="checkbox" checked={matchCase} onChange={(e) => setMatchCase(e.target.checked)} />
          Phân biệt hoa thường
        </label>
        <button className="btn btn-sm" onClick={findNextMatch} disabled={!find}>
          Tìm tiếp
        </button>
        <button className="btn btn-sm" onClick={replaceOne} disabled={!find}>
          Thay
        </button>
        <button
          className="btn btn-sm"
          onClick={() => setDraft(replaceAll(draft, find, replacement, matchCase))}
          disabled={!matches}
        >
          Thay tất cả{find ? ` (${matches})` : ""}
        </button>
      </div>

      {lowIdx.length > 0 && (
        <div className={`row ${s.lowList}`}>
          <span className="muted">{lowIdx.length} dòng có độ tin cậy thấp cần xem lại.</span>
          <button className="btn btn-sm" onClick={gotoLow}>
            Tới dòng tin cậy thấp kế tiếp
          </button>
        </div>
      )}

      <textarea
        ref={area}
        className={`textarea ${s.editor}`}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={onKeyDown}
        onSelect={syncHighlight}
        onClick={syncHighlight}
        onKeyUp={syncHighlight}
        aria-label="Nội dung OCR"
        spellCheck={false}
      />
      <div className="row">
        <button className="btn btn-primary" onClick={submit} disabled={save.isPending || conflict}>
          {save.isPending ? "Đang lưu..." : "Lưu phiên bản mới"}
        </button>
        <button className="btn" onClick={() => leave(`${base}/${page.page_number}`)}>
          Hủy
        </button>
        <button className="btn" onClick={() => setShowDiff((v) => !v)} aria-pressed={showDiff}>
          {showDiff ? "Ẩn khác biệt" : "Xem khác biệt với bản OCR"}
        </button>
        <span className="muted">
          Sửa trên v{baseVersion}
          {dirty ? " · có thay đổi chưa lưu" : ""} · Ctrl+S để lưu
        </span>
      </div>
      <div className="row">
        <button
          className="btn btn-sm"
          disabled={page.page_number <= 1}
          onClick={() => leave(`${base}/${page.page_number - 1}/edit`)}
        >
          <ChevronLeft size={14} aria-hidden /> Trang trước
        </button>
        <button
          className="btn btn-sm"
          disabled={page.page_number >= page.total_pages}
          onClick={() => leave(`${base}/${page.page_number + 1}/edit`)}
        >
          Trang sau <ChevronRight size={14} aria-hidden />
        </button>
      </div>
      {showDiff && (
        <div className={s.diff} aria-label="Khác biệt với bản OCR thô">
          {diffLines(page.raw_text, draft).map((op, i) => (
            <div key={i} className={op.kind === "add" ? s.diffAdd : op.kind === "del" ? s.diffDel : undefined}>
              {op.kind === "add" ? "+ " : op.kind === "del" ? "- " : "  "}
              {op.text}
            </div>
          ))}
        </div>
      )}
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
  const [active, setActive] = useState<number[] | null>(null);
  const [zoom, setZoom] = useState(1);
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
            <div className={`stack ${s.sticky}`}>
              <div className="row">
                <button
                  className="btn btn-sm btn-icon"
                  aria-label="Thu nhỏ ảnh"
                  onClick={() => setZoom((z) => Math.max(1, z - 0.5))}
                  disabled={zoom <= 1}
                >
                  <ZoomOut size={16} aria-hidden />
                </button>
                <span className="muted">{Math.round(zoom * 100)}%</span>
                <button
                  className="btn btn-sm btn-icon"
                  aria-label="Phóng to ảnh"
                  onClick={() => setZoom((z) => Math.min(3, z + 0.5))}
                  disabled={zoom >= 3}
                >
                  <ZoomIn size={16} aria-hidden />
                </button>
              </div>
              <PageImage
                documentId={id}
                pageNumber={p.page_number}
                width={p.width}
                height={p.height}
                query=""
                highlight={active}
                zoom={zoom}
              />
            </div>
          )}
          <EditorForm key={`${p.page_number}`} documentId={id} page={p} onActiveBox={setActive} />
        </div>
      )}
    </div>
  );
}
