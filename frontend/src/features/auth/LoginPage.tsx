import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, EyeOff, LockKeyhole, UserRound } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation } from "react-router";

import { ApiError } from "@/shared/api/client";
import { ErrorBox, Field } from "@/shared/components/ui";
import { replaceSession, useSession } from "@/shared/session";

import { getAuthOptions, login } from "./api";
import s from "./auth.module.css";
import { AuthShell } from "./AuthShell";

export function LoginPage() {
  const { session } = useSession();
  const client = useQueryClient();
  const location = useLocation();
  const back = location.state as { from?: string; uid?: string | null } | null;
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  // v0.17: chỉ hiện "Quên mật khẩu?" khi máy chủ đã cấu hình gửi email
  const options = useQuery({ queryKey: ["auth-options"], queryFn: getAuthOptions, staleTime: 5 * 60_000 });
  const canReset = options.data?.password_reset === true;

  const mutation = useMutation({
    mutationFn: () => login(username.trim(), password),
    // Chỉ ghi session; <Navigate> bên dưới chuyển trang khi session có giá trị. Gọi thêm navigate() ở đây
    // tạo hai lần điều hướng chồng nhau -> trang đích mount hai lần (từng làm App.test chập chờn trên CI).
    onSuccess: (data) => replaceSession(client, data),
  });

  if (session) {
    // Quay lại trang đang mở khi phiên hết hạn / mở link sâu; nhưng sau khi người A đăng xuất (hoặc hết phiên),
    // người B đăng nhập trên cùng tab thì về Tổng quan, không mở trang của A.
    const sameUser = !back?.uid || back.uid === session.user.id;
    const from = back?.from?.startsWith("/") && !back.from.startsWith("//") ? back.from : "/";
    return <Navigate to={sameUser ? from : "/"} replace />;
  }

  const submit = (e: FormEvent) => {
    e.preventDefault();
    mutation.mutate();
  };

  const locked = mutation.error instanceof ApiError && mutation.error.code === "ACCOUNT_LOCKED";

  return (
    <AuthShell>
      <form className={s.form} onSubmit={submit}>
        <div>
          <h1>Đăng nhập</h1>
          <p className="muted">Dùng tên đăng nhập hoặc email được cấp.</p>
        </div>
        <ErrorBox error={mutation.error} />
        {locked && canReset && (
          <p className={s.hint}>
            Bạn có thể dùng <Link to="/forgot-password">Quên mật khẩu</Link> để đặt mật khẩu mới qua email; tài khoản sẽ
            được mở lại sau khi đặt mật khẩu mới.
          </p>
        )}
        <Field label="Tên đăng nhập hoặc email" htmlFor="username">
          <div className={s.inputIcon}>
            <UserRound size={17} aria-hidden />
            <input
              id="username"
              className="input"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </div>
        </Field>
        <Field label="Mật khẩu" htmlFor="password">
          <div className={s.inputIcon}>
            <LockKeyhole size={17} aria-hidden />
            <input
              id="password"
              className="input"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            {/* Nhãn không chứa chữ "mật khẩu": E2E tìm ô nhập bằng get_by_label("Mật khẩu") (khớp chuỗi con) */}
            <button
              type="button"
              className={s.reveal}
              onClick={() => setShowPassword(!showPassword)}
              aria-label="Hiện ký tự đã nhập"
              aria-pressed={showPassword}
              title={showPassword ? "Ẩn" : "Hiện"}
            >
              {showPassword ? <EyeOff size={17} aria-hidden /> : <Eye size={17} aria-hidden />}
            </button>
          </div>
        </Field>
        {canReset && (
          <div className={s.forgotRow}>
            <Link to="/forgot-password">Quên mật khẩu?</Link>
          </div>
        )}
        <button className={`btn btn-primary ${s.submit}`} type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? "Đang đăng nhập..." : "Đăng nhập"}
        </button>
      </form>
    </AuthShell>
  );
}
