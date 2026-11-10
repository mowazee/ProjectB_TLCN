import { useEffect, useRef, useState } from "react";

import { pageImageUrl } from "@/features/documents";
import { SlotList, useSlots } from "@/shared/slots";

import s from "./ocr.module.css";

/** Ảnh trang + lớp phủ từ slot pageOverlays (P2-02 highlight). Tỉ lệ = chiều rộng hiển thị / chiều rộng ảnh gốc. */
export function PageImage({
  documentId,
  pageNumber,
  width,
  height,
  query,
  highlight = null,
  zoom = 1,
}: {
  documentId: string;
  pageNumber: number;
  width: number;
  height: number;
  query: string;
  /** OCR Editor (FR-05 v0.13): khung dòng đang chọn [x, y, w, h] theo pixel ảnh gốc */
  highlight?: number[] | null;
  /** Phóng to trong khung cuộn (1 = vừa chiều rộng) */
  zoom?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(0);
  const { pageOverlays } = useSlots();

  useEffect(() => {
    const el = ref.current;
    if (!el || !width) return;
    const update = () => setScale(el.clientWidth / width);
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, [width]);

  const image = (
    <div ref={ref} className={s.viewer} style={zoom !== 1 ? { width: `${zoom * 100}%` } : undefined}>
      <img src={pageImageUrl(documentId, pageNumber)} alt={`Trang ${pageNumber}`} width={width} height={height} />
      {scale > 0 && highlight && highlight.length === 4 && (
        <div
          className={s.lineMark}
          data-testid="line-highlight"
          style={{
            left: highlight[0] * scale,
            top: highlight[1] * scale,
            width: highlight[2] * scale,
            height: highlight[3] * scale,
          }}
        />
      )}
      {scale > 0 && (
        <div className={s.overlay}>
          <SlotList
            items={pageOverlays}
            props={{ documentId, pageNumber, imageWidth: width, imageHeight: height, scale, query }}
          />
        </div>
      )}
    </div>
  );
  return zoom !== 1 ? <div className={s.zoomBox}>{image}</div> : image;
}
