import { useMutation, useQuery } from "@tanstack/react-query";
import { CircleCheck, KeyRound, LockKeyhole, UserRound } from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";
import { Link, useParams } from "react-router";

import { ErrorBox, Field, Loading } from "@/shared/components/ui";

import { checkResetLink, forgotPassword, getAuthOptions, resetPassword } from "./api";
import s from "./auth.module.css";
import { AuthShell } from "./AuthShell";

const MIN_PASSWORD = 8;

function BackToLogin() {
  return (
    <p className={s.backRow}>
      <Link to="/login">Quay lại đăng nhập</Link>
    </p>
  );
}

function Notice({ children }: { children: ReactNode }) {
  return (
    <div className={s.notice} role="status">
      <CircleCheck size={18} aria-hidden />
      <div>{children}</div>
    </div>
  );
}

/** v0.17: nhập tên đăng nhập hoặc email để nhận link khôi phục mật khẩu (hiệu lực 30 phút). */
export function ForgotPasswordPage() {
  const [login, setLogin] = useState("");
  const options = useQuery({ queryKey: ["auth-options"], queryFn: getAuthOptions, staleTime: 5 * 60_000 });
  const mutation = useMutation({ mutationFn: () => forgotPassword(login.trim()) });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    mutation.mutate();
  };
  const minutes = options.data?.password_reset_ttl_minutes ?? 30;

  return (
    <AuthShell>
      <form className={s.form} onSubmit={submit}>
        <div>
          <h1>Quên mật khẩu</h1>
          <p className="muted">
            Nhập tên đăng nhập hoặc email của tài khoản. Hệ thống gửi link đặt lại mật khẩu tới email đã đăng ký, link
            có hiệu lực {minutes} phút.
          </p>
        </div>
        {options.data && !options.data.password_reset && (
          <ErrorBox error={new Error("Hệ thống chưa cấu hình gửi email, vui lòng liên hệ Quản trị viên.")} />
        )}
        <ErrorBox error={mutation.error} />
        {mutation.isSuccess ? (
          <Notice>
            {mutation.data.message} Hãy kiểm tra hộp thư (cả mục thư rác). Nếu tài khoản đang bị khóa do nhập sai mật
            khẩu, tài khoản sẽ được mở lại sau khi bạn đặt mật khẩu mới.
          </Notice>
        ) : (
          <>
            <Field label="Tên đăng nhập hoặc email" htmlFor="forgot-login">
              <div className={s.inputIcon}>
                <UserRound size={17} aria-hidden />
                <input
                  id="forgot-login"
                  className="input"
                  autoComplete="username"
                  value={login}
                  onChange={(e) => setLogin(e.target.value)}
                  required
                />
              </div>
            </Field>
            <button
              className={`btn btn-primary ${s.submit}`}
              type="submit"
              disabled={mutation.isPending || options.data?.password_reset === false}
            >
              {mutation.isPending ? "Đang gửi..." : "Gửi link khôi phục"}
            </button>
          </>
        )}
        <BackToLogin />
      </form>
    </AuthShell>
  );
}

/** v0.17: mở từ link trong email; đặt mật khẩu mới, tài khoản bị khóa do nhập sai được mở lại. */
export function ResetPasswordPage() {
  const { token = "" } = useParams();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);
  const link = useQuery({ queryKey: ["reset-link", token], queryFn: () => checkResetLink(token), retry: false });
  const mutation = useMutation({ mutationFn: () => resetPassword(token, password) });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (password.length < MIN_PASSWORD) {
      setLocalError(`Mật khẩu mới phải có ít nhất ${MIN_PASSWORD} ký tự.`);
      return;
    }
    if (password !== confirm) {
      setLocalError("Mật khẩu nhập lại không khớp.");
      return;
    }
    setLocalError(null);
    mutation.mutate();
  };

  let body: ReactNode;
  if (link.isPending) {
    body = <Loading />;
  } else if (mutation.isSuccess) {
    body = (
      <>
        <Notice>
          {mutation.data.reactivated
            ? "Đã đặt mật khẩu mới và mở khóa tài khoản. Bạn có thể đăng nhập bằng mật khẩu mới."
            : "Đã đặt mật khẩu mới. Bạn có thể đăng nhập bằng mật khẩu mới."}
        </Notice>
        <Link className={`btn btn-primary ${s.submit}`} to="/login">
          Đăng nhập
        </Link>
      </>
    );
  } else if (link.isError) {
    body = (
      <>
        <ErrorBox error={link.error} />
        <p className="muted">
          Link chỉ dùng được một lần và có hiệu lực trong thời gian giới hạn.{" "}
          <Link to="/forgot-password">Gửi lại link khôi phục</Link>.
        </p>
      </>
    );
  } else {
    body = (
      <>
        <p className="muted">
          Tài khoản: <strong>{link.data.username}</strong>
        </p>
        <ErrorBox error={localError ? new Error(localError) : mutation.error} />
        <Field label="Mật khẩu mới" htmlFor="new-password" hint={`Ít nhất ${MIN_PASSWORD} ký tự`}>
          <div className={s.inputIcon}>
            <LockKeyhole size={17} aria-hidden />
            <input
              id="new-password"
              className="input"
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
        </Field>
        <Field label="Nhập lại mật khẩu mới" htmlFor="confirm-password">
          <div className={s.inputIcon}>
            <KeyRound size={17} aria-hidden />
            <input
              id="confirm-password"
              className="input"
              type="password"
              autoComplete="new-password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required
            />
          </div>
        </Field>
        <button className={`btn btn-primary ${s.submit}`} type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? "Đang lưu..." : "Đặt mật khẩu mới"}
        </button>
      </>
    );
  }

  return (
    <AuthShell>
      <form className={s.form} onSubmit={submit}>
        <div>
          <h1>Đặt lại mật khẩu</h1>
        </div>
        {body}
        <BackToLogin />
      </form>
    </AuthShell>
  );
}
