import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Navigate, useLocation } from "react-router";

import { ErrorBox, Field } from "@/shared/components/ui";
import { replaceSession, useSession } from "@/shared/session";

import { login } from "./api";
import s from "./auth.module.css";

export function LoginPage() {
  const { session } = useSession();
  const client = useQueryClient();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? "/";
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const mutation = useMutation({
    mutationFn: () => login(username.trim(), password),
    // Chỉ ghi session; <Navigate> bên dưới chuyển trang khi session có giá trị. Gọi thêm navigate() ở đây
    // tạo hai lần điều hướng chồng nhau -> trang đích mount hai lần (từng làm App.test chập chờn trên CI).
    onSuccess: (data) => replaceSession(client, data),
  });

  if (session) return <Navigate to={from} replace />;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    mutation.mutate();
  };

  return (
    <div className={s.wrap}>
      <form className={`card ${s.form}`} onSubmit={submit}>
        <h1>Số hóa hồ sơ tài liệu</h1>
        <p className="muted">Đăng nhập bằng tên đăng nhập hoặc email.</p>
        <ErrorBox error={mutation.error} />
        <Field label="Tên đăng nhập hoặc email" htmlFor="username">
          <input
            id="username"
            className="input"
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            autoFocus
          />
        </Field>
        <Field label="Mật khẩu" htmlFor="password">
          <input
            id="password"
            className="input"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </Field>
        <button className="btn btn-primary" type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? "Đang đăng nhập..." : "Đăng nhập"}
        </button>
      </form>
    </div>
  );
}
