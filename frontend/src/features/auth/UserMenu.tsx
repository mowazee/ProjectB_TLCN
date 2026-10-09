import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router";

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
  return (
    <div className={s.user}>
      <div>
        <span>{session.user.full_name}</span>
        <div className="muted">{session.roles.map((r) => ROLE_LABELS[r] ?? r).join(", ")}</div>
      </div>
      <button className="btn btn-sm" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
        Đăng xuất
      </button>
    </div>
  );
}
