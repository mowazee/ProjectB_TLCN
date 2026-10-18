import { useMutation, useQueryClient } from "@tanstack/react-query";
import { LogOut } from "lucide-react";
import { Link, useNavigate } from "react-router";

import { ROLE_LABELS } from "@/shared/lib/format";
import { replaceSession, useSession } from "@/shared/session";

import { logout } from "./api";
import s from "./auth.module.css";

export function UserMenu() {
  const { session } = useSession();
  const client = useQueryClient();
  const navigate = useNavigate();
  const mutation = useMutation({
    mutationFn: logout,
    onSettled: () => {
      replaceSession(client, null); // logout xóa cache (SDD mục 15)
      navigate("/login", { replace: true });
    },
  });
  if (!session) return null;
  const name = session.user.full_name;
  // Chữ cái đầu của hai từ cuối (tên người Việt: "Nguyễn Văn An" -> "VA")
  const initials = name
    .trim()
    .split(/\s+/)
    .slice(-2)
    .map((w) => w[0])
    .join("")
    .toUpperCase();
  return (
    <div className={s.user}>
      <Link to="/account" className={s.me} title="Tài khoản của tôi">
        <span className={s.avatar} aria-hidden>
          {initials}
        </span>
        <div className={s.who}>
          <span>{name}</span>
          <small>{session.roles.map((r) => ROLE_LABELS[r] ?? r).join(", ")}</small>
        </div>
      </Link>
      <button
        className="btn btn-ghost btn-icon"
        onClick={() => mutation.mutate()}
        disabled={mutation.isPending}
        aria-label="Đăng xuất"
        title="Đăng xuất"
      >
        <LogOut size={18} aria-hidden />
      </button>
    </div>
  );
}
