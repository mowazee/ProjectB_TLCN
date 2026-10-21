import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, CircleDashed, FolderCheck, Sparkles, UserRound, type LucideIcon } from "lucide-react";
import { useEffect, useRef } from "react";

import { api } from "@/shared/api/client";
import type { Suggestion, Suggestions } from "@/shared/api/types";
import { EmptyState, ErrorBox, JobBadge, Loading } from "@/shared/components/ui";
import type { DocumentSlotProps } from "@/shared/types/feature";

import s from "./classification.module.css";

const ACTIVE = ["queued", "processing"];

/** D-10: nguồn của danh mục đang áp dụng. */
const SOURCES: Record<string, { label: string; icon: LucideIcon; tone: string }> = {
  user: { label: "Người dùng chọn", icon: UserRound, tone: "slate" },
  auto: { label: "Tự động phân loại", icon: Sparkles, tone: "violet" },
  pending: { label: "Chờ phân loại", icon: CircleDashed, tone: "amber" },
};

/** P2-05 (UC-22): tối đa 3 gợi ý kèm điểm. Tài liệu tải lên ở chế độ Danh mục gợi ý được tự áp dụng gợi ý cao nhất
 *  (D-10); còn lại chỉ đổi khi người dùng bấm Áp dụng. Tại một thời điểm chỉ một danh mục đang áp dụng: dòng đang áp
 *  dụng so theo danh mục của tài liệu (cùng nguồn với khối "Danh mục đang áp dụng"). */
export function SuggestionsTab({ document }: DocumentSlotProps) {
  const client = useQueryClient();
  const pending = document.category_source === "pending";
  const ocrActive = ACTIVE.includes(document.job_status ?? "");
  const data = useQuery({
    queryKey: ["suggestions", document.id],
    queryFn: () => api<Suggestions>(`/api/documents/${document.id}/category-suggestions`),
    // OCR chưa xong, đang phân loại, hoặc chờ phân loại mà job CLASSIFY chưa tạo: hỏi lại định kỳ
    refetchInterval: (q) => {
      const status = q.state.data?.job_status;
      return ocrActive || (status && ACTIVE.includes(status)) || (pending && !status) ? 3000 : false;
    },
  });
  const accept = useMutation({
    mutationFn: (categoryId: number) =>
      api<Suggestion>(`/api/documents/${document.id}/category-suggestions/accept`, {
        method: "POST",
        json: { category_id: categoryId },
      }),
    // chờ tải lại cả tài liệu và gợi ý rồi mới mở lại nút: không có lúc hai dòng cùng "Đang áp dụng"
    onSuccess: () =>
      Promise.all([
        client.invalidateQueries({ queryKey: ["suggestions", document.id] }),
        client.invalidateQueries({ queryKey: ["documents"] }),
      ]),
  });

  // job vừa xong: tài liệu có thể vừa được tự phân loại -> tải lại danh mục của tài liệu. Không đòi phải thấy
  // queued/processing trước: job chạy nhanh thì lần hỏi đầu đã là completed trong khi tài liệu còn "chờ" (bản cũ).
  const status = data.data?.job_status;
  const prev = useRef(status);
  useEffect(() => {
    const justCompleted = status === "completed" && prev.current !== "completed";
    if (justCompleted && (pending || (prev.current && ACTIVE.includes(prev.current)))) {
      client.invalidateQueries({ queryKey: ["documents"] });
    }
    prev.current = status;
  }, [status, pending, client]);

  // ngược lại: trang chi tiết tải lại tài liệu trước (vd. đã tự phân loại) -> tải lại gợi ý cho khớp
  const assigned = `${document.category.id}:${document.category_source}`;
  const prevAssigned = useRef(assigned);
  useEffect(() => {
    if (prevAssigned.current !== assigned) {
      client.invalidateQueries({ queryKey: ["suggestions", document.id] });
    }
    prevAssigned.current = assigned;
  }, [assigned, document.id, client]);

  if (data.isPending) return <Loading />;
  if (data.error || !data.data) return <ErrorBox error={data.error} />;
  const items = data.data.items;
  const source = SOURCES[document.category_source] ?? SOURCES.user;
  const SourceIcon = source.icon;
  const current = items.find((x) => x.category_id === document.category.id);
  const finished = status === "completed" || status === "failed";

  return (
    <div className={s.wrap}>
      <section className={s.summary} aria-label="Danh mục đang áp dụng">
        <div className={s.summaryMain}>
          <h3 className={s.eyebrow}>Danh mục đang áp dụng</h3>
          <div className={s.current}>
            <span className={`${s.tile} ${s[source.tone]}`}>
              <FolderCheck size={20} aria-hidden />
            </span>
            <div className={s.currentText}>
              <strong className={s.currentName}>{document.category.name}</strong>
              <span className={s.meta}>
                <span className={`${s.pill} ${s[source.tone]}`}>
                  <SourceIcon size={13} aria-hidden /> {source.label}
                </span>
                {current && <span className="muted">Độ tin cậy {(current.score * 100).toFixed(0)}%</span>}
              </span>
            </div>
          </div>
        </div>
        <div className={s.summarySide}>
          <h3 className={s.eyebrow}>Phân loại tự động</h3>
          <JobBadge status={status} />
        </div>
      </section>

      {pending && finished && (
        <p className={s.notice} role="status">
          Hệ thống chưa đủ chắc chắn để tự chọn danh mục. Hãy áp dụng một gợi ý bên dưới hoặc chọn danh mục ở Sửa thông
          tin.
        </p>
      )}
      <ErrorBox error={accept.error} />

      <section aria-labelledby="sugg-title">
        <h3 className={s.eyebrow} id="sugg-title">
          Danh mục gợi ý
        </h3>
        {!items.length ? (
          <EmptyState>
            {pending && !finished
              ? "Đang chờ OCR xong để phân loại…"
              : "Chưa có gợi ý (cần OCR xong và đủ dữ liệu mẫu)."}
          </EmptyState>
        ) : (
          <ul className={s.list}>
            {items.map((x) => {
              const applied = x.category_id === document.category.id;
              const pct = Math.round(x.score * 100);
              return (
                <li key={x.category_id} className={`${s.item} ${applied ? s.itemApplied : ""}`}>
                  <div className={s.itemText}>
                    <strong>{x.name}</strong>
                    <div
                      className={s.bar}
                      role="meter"
                      aria-valuenow={pct}
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-label={`Điểm ${x.name}`}
                      title="Xác suất mô hình TF-IDF + Logistic Regression ước lượng; chỉ là gợi ý"
                    >
                      <span style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                  <span className={s.score}>{pct}%</span>
                  <div className={s.action}>
                    {applied ? (
                      <span className={s.applied}>
                        <Check size={14} aria-hidden /> Đang áp dụng
                      </span>
                    ) : (
                      document.can_edit && (
                        <button
                          className="btn btn-sm"
                          onClick={() => accept.mutate(x.category_id)}
                          disabled={accept.isPending}
                        >
                          Áp dụng
                        </button>
                      )
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}
