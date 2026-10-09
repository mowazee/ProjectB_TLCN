import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/shared/api/client";
import type { Suggestion, Suggestions } from "@/shared/api/types";
import { Badge, EmptyState, ErrorBox, JobBadge, Loading } from "@/shared/components/ui";
import type { DocumentSlotProps } from "@/shared/types/feature";

/** P2-05 (UC-22): tối đa 3 gợi ý kèm điểm; KHÔNG tự đổi danh mục - chỉ đổi khi người dùng chấp nhận. */
export function SuggestionsTab({ document }: DocumentSlotProps) {
  const client = useQueryClient();
  const data = useQuery({
    queryKey: ["suggestions", document.id],
    queryFn: () => api<Suggestions>(`/api/documents/${document.id}/category-suggestions`),
  });
  const accept = useMutation({
    mutationFn: (categoryId: number) =>
      api<Suggestion>(`/api/documents/${document.id}/category-suggestions/accept`, {
        method: "POST",
        json: { category_id: categoryId },
      }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["suggestions", document.id] });
      client.invalidateQueries({ queryKey: ["documents"] });
    },
  });

  if (data.isPending) return <Loading />;
  if (data.error || !data.data) return <ErrorBox error={data.error} />;
  return (
    <div className="stack">
      <div className="row">
        <span className="muted">Phân loại tự động:</span>
        <JobBadge status={data.data.job_status} />
        <span className="muted">Danh mục hiện tại: {document.category.name}</span>
      </div>
      <ErrorBox error={accept.error} />
      {!data.data.items.length ? (
        <EmptyState>Chưa có gợi ý (cần OCR xong và đủ dữ liệu mẫu).</EmptyState>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Danh mục gợi ý</th>
              <th title="Xác suất mô hình TF-IDF + Logistic Regression ước lượng; chỉ là gợi ý">Điểm</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {data.data.items.map((s) => (
              <tr key={s.category_id}>
                <td>{s.name}</td>
                <td>{(s.score * 100).toFixed(0)}%</td>
                <td>
                  {s.is_current ? (
                    <Badge tone="ok">Đang dùng</Badge>
                  ) : (
                    document.can_edit && (
                      <button
                        className="btn btn-sm btn-primary"
                        onClick={() => accept.mutate(s.category_id)}
                        disabled={accept.isPending}
                      >
                        Chấp nhận
                      </button>
                    )
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
