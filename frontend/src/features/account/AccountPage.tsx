import { CircleCheck, KeyRound, UserRound } from "lucide-react";
import { useState, type FormEvent } from "react";

import type { Account } from "@/shared/api/types";
import { ErrorBox, Field, Loading, PageHeader } from "@/shared/components/ui";
import { ROLE_LABELS, formatDateTime } from "@/shared/lib/format";

import { useAccount, useChangePassword, useUpdateAccount } from "./api";
import s from "./account.module.css";

const MIN_PASSWORD = 8; // khớp users/application/account.py

function Done({ children }: { children: string }) {
  return (
    <span className={s.done} role="status">
      <CircleCheck size={16} aria-hidden /> {children}
    </span>
  );
}

function ProfileCard({ account }: { account: Account }) {
  const save = useUpdateAccount();
  const [fullName, setFullName] = useState(account.full_name);
  const [phone, setPhone] = useState(account.phone ?? "");
  const dirty = fullName.trim() !== account.full_name || (phone.trim() || null) !== account.phone;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    save.mutate({ full_name: fullName.trim(), phone: phone.trim() || null });
  };

  return (
    <section className="card">
      <h2 className={s.title}>
        <UserRound size={18} aria-hidden /> Thông tin cá nhân
      </h2>
      <dl className={s.facts}>
        <dt>Tên đăng nhập</dt>
        <dd>{account.username}</dd>
        <dt>Email</dt>
        <dd>{account.email}</dd>
        <dt>Vai trò</dt>
        <dd>{account.roles.map((r) => ROLE_LABELS[r] ?? r).join(", ")}</dd>
        <dt>Phòng ban</dt>
        <dd>{account.department_name ?? "—"}</dd>
        <dt>Đăng nhập gần nhất</dt>
        <dd>{formatDateTime(account.last_login_at)}</dd>
      </dl>
      <p className="muted">Tên đăng nhập, email, vai trò và phòng ban do Quản trị viên thay đổi.</p>
      <form className="stack" onSubmit={submit}>
        <ErrorBox error={save.error} />
        <Field label="Họ tên" htmlFor="acc-name">
          <input
            id="acc-name"
            className="input"
            value={fullName}
            maxLength={100}
            onChange={(e) => setFullName(e.target.value)}
            required
          />
        </Field>
        <Field label="Điện thoại" htmlFor="acc-phone">
          <input
            id="acc-phone"
            className="input"
            value={phone}
            maxLength={20}
            onChange={(e) => setPhone(e.target.value)}
          />
        </Field>
        <div className="row">
          <button className="btn btn-primary" type="submit" disabled={!dirty || save.isPending}>
            Lưu thay đổi
          </button>
          {save.isSuccess && !dirty && <Done>Đã lưu</Done>}
        </div>
      </form>
    </section>
  );
}

function PasswordCard() {
  const change = useChangePassword();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const tooShort = next.length > 0 && next.length < MIN_PASSWORD;
  const mismatch = confirm.length > 0 && confirm !== next;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (tooShort || confirm !== next) return;
    change.mutate(
      { current_password: current, new_password: next },
      {
        onSuccess: () => {
          setCurrent("");
          setNext("");
          setConfirm("");
        },
      },
    );
  };

  return (
    <section className="card">
      <h2 className={s.title}>
        <KeyRound size={18} aria-hidden /> Đổi mật khẩu
      </h2>
      <p className="muted">
        Sau khi đổi, bạn sẽ bị đăng xuất khỏi mọi thiết bị khác; phiên trên trình duyệt này được giữ.
      </p>
      <form className="stack" onSubmit={submit}>
        <ErrorBox error={change.error} />
        <Field label="Mật khẩu hiện tại" htmlFor="pw-cur">
          <input
            id="pw-cur"
            className="input"
            type="password"
            autoComplete="current-password"
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
            required
          />
        </Field>
        <Field
          label="Mật khẩu mới"
          htmlFor="pw-new"
          hint={`Ít nhất ${MIN_PASSWORD} ký tự, khác mật khẩu hiện tại`}
          error={tooShort ? `Cần ít nhất ${MIN_PASSWORD} ký tự` : undefined}
        >
          <input
            id="pw-new"
            className="input"
            type="password"
            autoComplete="new-password"
            value={next}
            onChange={(e) => setNext(e.target.value)}
            required
          />
        </Field>
        <Field
          label="Nhập lại mật khẩu mới"
          htmlFor="pw-confirm"
          error={mismatch ? "Mật khẩu nhập lại không khớp" : undefined}
        >
          <input
            id="pw-confirm"
            className="input"
            type="password"
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            required
          />
        </Field>
        <div className="row">
          <button
            className="btn btn-primary"
            type="submit"
            disabled={change.isPending || !current || !next || tooShort || confirm !== next}
          >
            Đổi mật khẩu
          </button>
          {change.isSuccess && <Done>Đã đổi mật khẩu, các thiết bị khác đã bị đăng xuất</Done>}
        </div>
      </form>
    </section>
  );
}

/** UC-25 (FR-09): tài khoản của chính người dùng. */
export function AccountPage() {
  const account = useAccount();
  return (
    <div>
      <PageHeader icon={UserRound} title="Tài khoản của tôi" />
      <ErrorBox error={account.error} />
      {account.isPending ? (
        <Loading />
      ) : account.data ? (
        <div className={s.layout}>
          <ProfileCard account={account.data} />
          <PasswordCard />
        </div>
      ) : null}
    </div>
  );
}
