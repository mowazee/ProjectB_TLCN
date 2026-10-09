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
}: {
  documentId: string;
  pageNumber: number;
  width: number;
  height: number;
  query: string;
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

  return (
    <div ref={ref} className={s.viewer}>
      <img src={pageImageUrl(documentId, pageNumber)} alt={`Trang ${pageNumber}`} width={width} height={height} />
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
}
