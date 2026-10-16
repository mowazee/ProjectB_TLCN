import { ChevronLeft, ChevronRight } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { api } from "@/shared/api/client";
import type { Highlights } from "@/shared/api/types";
import type { PageOverlayProps } from "@/shared/types/feature";

import s from "./highlight.module.css";

const REASONS: Record<string, string> = {
  empty_query: "",
  no_ocr: "Trang chưa có kết quả OCR.",
  no_boxes: "Trang không có tọa độ chữ nên không đánh dấu được (vẫn xem được nội dung).",
  text_modified: "Trang đã được chỉnh sửa nên vị trí chữ trên ảnh có thể lệch — không đánh dấu để tránh sai.",
  not_found: "Không tìm thấy từ khóa trên ảnh trang này (có thể nằm vắt qua hai dòng).",
};

/** P2-02: vẽ khung từ khóa trên ảnh trang theo ocr_results.boxes; tỉ lệ = scale của PageViewer. */
export function HighlightOverlay({ documentId, pageNumber, scale, query }: PageOverlayProps) {
  const q = query.trim();
  // Vị trí đang chọn gắn với (từ khóa, trang): đổi trang/từ khóa thì tự về kết quả đầu tiên
  const key = `${pageNumber}|${q}`;
  const [cursor, setCursor] = useState({ key, index: 0 });
  const active = cursor.key === key ? cursor.index : 0;
  const setActive = (index: number) => setCursor({ key, index });
  const activeRef = useRef<HTMLDivElement>(null);
  const result = useQuery({
    queryKey: ["highlights", documentId, pageNumber, q],
    enabled: q.length > 0,
    queryFn: () => api<Highlights>(`/api/documents/${documentId}/pages/${pageNumber}/highlights`, { query: { q } }),
  });

  useEffect(() => {
    activeRef.current?.scrollIntoView?.({ block: "center", behavior: "smooth" });
  }, [active, result.data]);

  if (!q || !result.data) return null;
  const { boxes, reason } = result.data;
  const total = boxes.length;

  return (
    <>
      {boxes.map((b, i) => (
        <div
          key={`${b.line}-${b.x}`}
          ref={i === active ? activeRef : undefined}
          className={`${s.box} ${i === active ? s.active : ""}`}
          data-testid="highlight-box"
          style={{ left: b.x * scale, top: b.y * scale, width: b.w * scale, height: b.h * scale }}
        />
      ))}
      <div className={s.controls}>
        {total > 0 ? (
          <>
            <span>
              “{q}”: {active + 1}/{total}
            </span>
            <button
              className="btn btn-sm"
              onClick={() => setActive((active - 1 + total) % total)}
              aria-label="Kết quả trước"
            >
              <ChevronLeft size={15} aria-hidden />
            </button>
            <button className="btn btn-sm" onClick={() => setActive((active + 1) % total)} aria-label="Kết quả sau">
              <ChevronRight size={15} aria-hidden />
            </button>
          </>
        ) : (
          <span>{REASONS[reason ?? ""] ?? "Không đánh dấu được."}</span>
        )}
      </div>
    </>
  );
}
