import { Search } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router";

import { api } from "@/shared/api/client";
import type { PageHit, Paged, SearchHit } from "@/shared/api/types";
import { EmptyState, ErrorBox, Loading, PageHeader, Pagination } from "@/shared/components/ui";
import { useCategories } from "@/shared/hooks/useCategories";
import { useDebounce } from "@/shared/hooks/useDebounce";

import s from "./search.module.css";

/** Đoạn trích với vùng khớp được đánh dấu bằng <mark> (vẫn render như text, không chèn HTML). */
export function Snippet({ hit }: { hit: PageHit }) {
  const { snippet, match_start: a, match_end: b } = hit;
  if (a < 0 || b <= a || b > snippet.length) return <span>{snippet}</span>;
  return (
    <span>
      {snippet.slice(0, a)}
      <mark>{snippet.slice(a, b)}</mark>
      {snippet.slice(b)}
    </span>
  );
}

export function SearchPage() {
  const [params, setParams] = useSearchParams();
  const [input, setInput] = useState(params.get("q") ?? "");
  const q = useDebounce(input.trim(), 400);
  const page = Number(params.get("page") ?? 1);
  const categoryId = params.get("category_id") ?? "";
  const categories = useCategories();

  useEffect(() => {
    const next = new URLSearchParams(params);
    if (q) next.set("q", q);
    else next.delete("q");
    if (q !== (params.get("q") ?? "")) next.delete("page");
    if (next.toString() !== params.toString()) setParams(next, { replace: true });
  }, [q, params, setParams]);

  const result = useQuery({
    queryKey: ["search", q, page, categoryId],
    enabled: q.length > 0,
    queryFn: () =>
      api<Paged<SearchHit>>("/api/search", {
        query: { q, page, page_size: 10, category_id: categoryId || undefined },
      }),
    placeholderData: (prev) => prev,
  });

  const setParam = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== "page") next.delete("page");
    setParams(next, { replace: true });
  };

  return (
    <div>
      <PageHeader
        icon={Search}
        title="Tìm kiếm nội dung"
        subtitle="Tìm trên text đã OCR/đã sửa, không phân biệt dấu và hoa thường."
      />
      <div className={s.bar}>
        <input
          className="input"
          type="search"
          placeholder="Nhập từ khóa, ví dụ: nghiệm thu công trình"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          autoFocus
          aria-label="Từ khóa"
        />
        <select
          className="select"
          value={categoryId}
          onChange={(e) => setParam("category_id", e.target.value)}
          aria-label="Danh mục"
        >
          <option value="">Mọi danh mục</option>
          {categories.data?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </div>
      <ErrorBox error={result.error} />
      {!q ? (
        <EmptyState>Nhập từ khóa để tìm kiếm.</EmptyState>
      ) : result.isPending ? (
        <Loading />
      ) : !result.data?.items.length ? (
        <EmptyState>Không tìm thấy kết quả cho “{q}”.</EmptyState>
      ) : (
        <>
          <div className="stack">
            {result.data.items.map((hit) => (
              <div key={hit.document_id} className="card">
                <div className="row">
                  <Link to={`/documents/${hit.document_id}`} className={s.title}>
                    {hit.title}
                  </Link>
                  <span className="muted">{hit.category_name}</span>
                  <span className="muted">· {hit.pages.length} trang khớp</span>
                </div>
                <ul className={s.pages}>
                  {hit.pages.map((p) => (
                    <li key={p.page_number}>
                      <Link to={`/documents/${hit.document_id}/pages/${p.page_number}?q=${encodeURIComponent(q)}`}>
                        Trang {p.page_number}
                      </Link>
                      : <Snippet hit={p} />
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
          <Pagination
            page={result.data.page}
            pageSize={result.data.page_size}
            total={result.data.total}
            onChange={(p) => setParam("page", String(p))}
          />
        </>
      )}
    </div>
  );
}
