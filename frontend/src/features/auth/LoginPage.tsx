import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Eye,
  EyeOff,
  FileSearch,
  History,
  LockKeyhole,
  ScanText,
  ShieldCheck,
  UserRound,
  Workflow,
} from "lucide-react";
import { useState, type FormEvent } from "react";
import { Navigate, useLocation } from "react-router";

import { ThemeToggle } from "@/shared/components/ThemeToggle";
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
  const [showPassword, setShowPassword] = useState(false);

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
      <section className={s.hero} aria-label="Giới thiệu hệ thống">
        <div className={s.heroBrand}>
          <span className={s.heroLogo}>
            <ScanText size={24} aria-hidden />
          </span>
          Số hóa hồ sơ
        </div>
        <div>
          <h2 className={s.heroTitle}>Hệ thống số hóa hồ sơ tài liệu doanh nghiệp</h2>
          <p className={s.heroLead}>Từ bản giấy đến dữ liệu tra cứu được trong vài phút.</p>
          <ul className={s.features}>
            {FEATURES.map(({ icon: Icon, title, text }) => (
              <li key={title}>
                <span>
                  <Icon size={18} aria-hidden />
                </span>
                <div>
                  <strong>{title}</strong>
                  {text}
                </div>
              </li>
            ))}
          </ul>
        </div>
        <small className={s.heroFoot}>Tiểu luận chuyên ngành · UTE · Nhóm 3</small>
      </section>
      <div className={s.side}>
        <ThemeToggle className={s.themeToggle} />
        <form className={s.form} onSubmit={submit}>
          <div>
            <h1>Đăng nhập</h1>
            <p className="muted">Dùng tên đăng nhập hoặc email được cấp.</p>
          </div>
          <ErrorBox error={mutation.error} />
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
                autoFocus
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
          <button className={`btn btn-primary ${s.submit}`} type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? "Đang đăng nhập..." : "Đăng nhập"}
          </button>
        </form>
      </div>
    </div>
  );
}

const FEATURES = [
  { icon: ScanText, title: "OCR tự động", text: "Nhận dạng chữ in và chữ viết tay tiếng Việt ngay sau khi tải lên." },
  { icon: FileSearch, title: "Tìm kiếm toàn văn", text: "Tìm theo nội dung, mở đúng trang và vị trí từ khóa." },
  { icon: Workflow, title: "Duyệt và mượn hồ sơ", text: "Quy trình gửi duyệt, xuất bản, mượn và trả bản cứng." },
  { icon: History, title: "Lưu vết đầy đủ", text: "Nhật ký mọi thao tác, so sánh phiên bản, khôi phục thay đổi." },
  {
    icon: ShieldCheck,
    title: "Phân quyền chặt chẽ",
    text: "Chỉ xem tài liệu của mình và phòng ban, kiểm tra tại máy chủ.",
  },
];
