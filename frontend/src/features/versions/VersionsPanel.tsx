import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "@/shared/api/client";
import type { Diff, VersionInfo } from "@/shared/api/types";
import { ErrorBox, Loading } from "@/shared/components/ui";
import { formatDateTime } from "@/shared/lib/format";
import type { EditorToolProps } from "@/shared/types/feature";

import s from "./versions.module.css";

export function DiffView({ diff }: { diff: Diff }) {
  if (diff.identical) return <p className="muted">Hai phiên bản giống nhau.</p>;
  return (
    <div className={s.diff}>
      {diff.hunks.map((h, i) => {
        if (h.op === "equal") {
          return h.old_lines.map((line, j) => (
            <div key={`${i}-${j}`} className={s.line}>
              {line || " "}
            </div>
          ));
        }
        if (h.op === "replace") {
          return (
            <div key={i} className={`${s.line} ${s.changed}`}>
              {h.words.map((w, j) =>
                w.op === "equal" ? (
                  <span key={j}>{w.old}</span>
                ) : (
                  <span key={j}>
                    {w.old && <del className={s.del}>{w.old}</del>}
                    {w.new && <ins className={s.ins}>{w.new}</ins>}
                  </span>
                ),
              )}
            </div>
          );
        }
        return (
          <div key={i}>
            {h.old_lines.map((line, j) => (
              <div key={`d${j}`} className={`${s.line} ${s.removed}`}>
                − {line}
              </div>
            ))}
            {h.new_lines.map((line, j) => (
              <div key={`a${j}`} className={`${s.line} ${s.added}`}>
                + {line}
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );
}

/** P2-06 (UC-12): chọn hai phiên bản (0 = OCR thô) để xem khác biệt theo dòng/từ; chỉ đọc. */
export function VersionsPanel({ documentId, pageNumber, currentVersion }: EditorToolProps) {
  const base = `/api/documents/${documentId}/pages/${pageNumber}/versions`;
  const versions = useQuery({
    queryKey: ["versions", documentId, pageNumber],
    queryFn: () => api<VersionInfo[]>(base),
  });
  const [from, setFrom] = useState(0);
  const [to, setTo] = useState(currentVersion);
  const diff = useQuery({
    queryKey: ["versions", documentId, pageNumber, "diff", from, to],
    enabled: from !== to,
    queryFn: () => api<Diff>(`${base}/diff`, { query: { from, to } }),
  });

  if (versions.isPending) return <Loading />;
  if (versions.error) return <ErrorBox error={versions.error} />;
  const list = versions.data ?? [];
  const label = (v: VersionInfo) =>
    v.is_raw
      ? `v0 - OCR gốc (${v.engine_version ?? ""})`
      : `v${v.version} - ${v.edited_by_name ?? "?"}, ${formatDateTime(v.edited_at)}`;

  return (
    <div className="card stack">
      <h3>So sánh phiên bản</h3>
      <div className="row">
        <select
          className="select"
          style={{ maxWidth: 320 }}
          value={from}
          onChange={(e) => setFrom(Number(e.target.value))}
          aria-label="Từ phiên bản"
        >
          {list.map((v) => (
            <option key={v.version} value={v.version}>
              {label(v)}
            </option>
          ))}
        </select>
        <span>→</span>
        <select
          className="select"
          style={{ maxWidth: 320 }}
          value={to}
          onChange={(e) => setTo(Number(e.target.value))}
          aria-label="Đến phiên bản"
        >
          {list.map((v) => (
            <option key={v.version} value={v.version}>
              {label(v)}
            </option>
          ))}
        </select>
      </div>
      {from === to ? (
        <p className="muted">Chọn hai phiên bản khác nhau.</p>
      ) : diff.isPending ? (
        <Loading />
      ) : diff.error ? (
        <ErrorBox error={diff.error} />
      ) : (
        diff.data && (
          <>
            <span className="muted">
              +{diff.data.lines_added} / −{diff.data.lines_removed} dòng
            </span>
            <DiffView diff={diff.data} />
          </>
        )
      )}
    </div>
  );
}
