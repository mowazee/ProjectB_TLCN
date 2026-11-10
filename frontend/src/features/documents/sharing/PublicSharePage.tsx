import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, FileText, KeyRound, ShieldCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useParams } from "react-router";

import { ApiError, api } from "@/shared/api/client";
import type { PublicShare } from "@/shared/api/types";
import { ErrorBox, Field, Loading } from "@/shared/components/ui";
import { ValidityBadge } from "@/shared/components/validity";
import { formatBytes, formatDateTime } from "@/shared/lib/format";

import s from "./sharing.module.css";

/** UC-33 (FR-18, SDD v0.13): người nhận ngoài hệ thống mở link, xác thực OTP qua email, xem và tải (nếu được phép).
 *  Trang nằm ngoài khung ứng dụng, không có menu; gọi API công khai với silent401 để không chuyển về /login. */
export function PublicSharePage() {
  const { token = "" } = useParams();
  const base = `/api/public/shares/${token}`;
  const client = useQueryClient();
  const share = useQuery({
    queryKey: ["public-share", token],
    queryFn: () => api<PublicShare>(base, { silent401: true }),
    retry: false,
  });
  const [code, setCode] = useState("");
  const send = useMutation({
    mutationFn: () => api<{ sent_to: string }>(`${base}/otp`, { method: "POST", silent401: true }),
  });
  const verify = useMutation({
    mutationFn: () => api(`${base}/verify`, { json: { code: code.trim() }, silent401: true }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["public-share", token] }),
  });

  if (share.isPending) return <Loading />;
  const gone = share.error instanceof ApiError && share.error.status === 410;
  const d = share.data;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    verify.mutate();
  };

  return (
    <main className={s.publicPage}>
      <div className={`card stack ${s.publicCard}`}>
        {gone ? (
          <>
            <h1>Link không còn hiệu lực</h1>
            <p className="muted">
              Link đã hết hạn, đã bị thu hồi hoặc tài liệu không còn được chia sẻ. Hãy liên hệ người gửi.
            </p>
          </>
        ) : !d ? (
          <ErrorBox error={share.error} />
        ) : !d.verified ? (
          <>
            <h1>
              <ShieldCheck size={22} aria-hidden /> {d.title}
            </h1>
            <p className="muted">
              Tài liệu được chia sẻ tới <strong>{d.recipient}</strong>. Để xem, bấm “Gửi mã” rồi nhập mã xác thực trong
              email. Link hết hạn lúc {formatDateTime(d.expires_at)}.
            </p>
            <div>
              <button className="btn" onClick={() => send.mutate()} disabled={send.isPending}>
                <KeyRound size={16} aria-hidden /> {send.isSuccess ? "Gửi lại mã" : "Gửi mã xác thực"}
              </button>
              {send.isSuccess && <span className="muted"> Đã gửi mã tới {send.data.sent_to}.</span>}
            </div>
            <ErrorBox error={send.error} />
            <form className="row" onSubmit={submit} style={{ alignItems: "flex-end" }}>
              <Field label="Mã xác thực" htmlFor="otp">
                <input
                  id="otp"
                  className="input"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  maxLength={10}
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  required
                />
              </Field>
              <button className="btn btn-primary" type="submit" disabled={verify.isPending || !code.trim()}>
                Xác nhận
              </button>
            </form>
            <ErrorBox error={verify.error} />
          </>
        ) : (
          <>
            <h1>
              <FileText size={22} aria-hidden /> {d.title}
            </h1>
            <p className="muted">
              Hiệu lực tài liệu: <ValidityBadge status={d.validity_status} validUntil={d.valid_until} /> · Link hết hạn
              lúc {formatDateTime(d.expires_at)}.
            </p>
            {d.allow_download ? (
              <div className="row">
                <a className="btn btn-primary" href={`${base}/file`} download>
                  <Download size={16} aria-hidden /> Tải file gốc{d.file_name ? ` (${d.file_name})` : ""}
                </a>
                {d.attachments.length > 0 && (
                  <a className="btn" href={`${base}/bundle`} download>
                    <Download size={16} aria-hidden /> Tải cả bộ (.zip)
                  </a>
                )}
              </div>
            ) : (
              <p className="muted">Link này chỉ cho phép xem, không cho tải.</p>
            )}
            {d.attachments.length > 0 && (
              <section className="stack">
                <h2 className={s.publicH2}>Tài liệu đi kèm</h2>
                <ul>
                  {d.attachments.map((a) => (
                    <li key={a.id}>
                      {d.allow_download ? (
                        <a href={`${base}/attachments/${a.id}`} download>
                          {a.file_name}
                        </a>
                      ) : (
                        a.file_name
                      )}{" "}
                      <span className="muted">· {formatBytes(a.bytes)}</span>
                    </li>
                  ))}
                </ul>
              </section>
            )}
            <section className="stack">
              {d.pages.map((p) => (
                <img
                  key={p.page_number}
                  className={s.publicImg}
                  src={`${base}/pages/${p.page_number}/image`}
                  alt={`Trang ${p.page_number}`}
                  width={p.width}
                  height={p.height}
                  loading="lazy"
                />
              ))}
            </section>
          </>
        )}
      </div>
    </main>
  );
}
