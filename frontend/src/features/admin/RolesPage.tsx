import {
  BriefcaseBusiness,
  ClipboardCheck,
  Eye,
  ShieldCheck,
  UserMinus,
  UserPlus,
  UsersRound,
  type LucideIcon,
} from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";

import type { User } from "@/shared/api/types";
import { Badge, EmptyState, ErrorBox, Loading, Modal, PageHeader } from "@/shared/components/ui";
import { ROLE_LABELS } from "@/shared/lib/format";
import { useSession } from "@/shared/session";

import { useDepartments, useRoleMembers, useRoles, useSaveUser, useUserPicker } from "./api";
import s from "./roles.module.css";

const ROLE_ICONS: Record<string, LucideIcon> = {
  ADMIN: ShieldCheck,
  OFFICER: BriefcaseBusiness,
  APPROVER: ClipboardCheck,
  VIEWER: Eye,
};

function AddMember({ role, onClose }: { role: string; onClose: () => void }) {
  const [q, setQ] = useState("");
  const users = useUserPicker(q);
  const save = useSaveUser();
  const candidates = (users.data?.items ?? []).filter((u) => !u.roles.includes(role));
  return (
    <Modal title={`Thêm thành viên: ${ROLE_LABELS[role] ?? role}`} onClose={onClose}>
      <div className="stack">
        <input
          className="input"
          placeholder="Tìm theo tên đăng nhập, họ tên, email..."
          value={q}
          onChange={(e) => setQ(e.target.value)}
          aria-label="Tìm người dùng"
          autoFocus
        />
        <ErrorBox error={save.error} />
        {users.isPending ? (
          <Loading />
        ) : candidates.length === 0 ? (
          <EmptyState icon={UsersRound}>Không còn người dùng phù hợp để thêm.</EmptyState>
        ) : (
          <ul className={s.pick}>
            {candidates.map((u) => (
              <li key={u.id}>
                <div>
                  <strong>{u.full_name}</strong>
                  <span className="muted"> @{u.username}</span>
                  <div className="muted">{u.roles.map((r) => ROLE_LABELS[r] ?? r).join(", ")}</div>
                </div>
                <button
                  className="btn btn-sm"
                  disabled={save.isPending}
                  onClick={() => save.mutate({ id: u.id, data: { roles: [...u.roles, role] } })}
                >
                  <UserPlus size={15} aria-hidden /> Thêm
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Modal>
  );
}

/** FR-12 (UC-28): 4 vai trò cố định (D-07); ma trận quyền chỉ đọc; thêm/gỡ thành viên. Server mới quyết định quyền. */
export function RolesPage() {
  const roles = useRoles();
  const departments = useDepartments();
  const { session } = useSession();
  const [selected, setSelected] = useState<string>("ADMIN");
  const [adding, setAdding] = useState(false);
  const members = useRoleMembers(selected);
  const save = useSaveUser();
  const depName = (id: number | null) => departments.data?.find((d) => d.id === id)?.name ?? "—";

  if (roles.isPending) return <Loading />;
  if (roles.error) return <ErrorBox error={roles.error} />;
  const role = roles.data?.find((r) => r.name === selected);

  const removeFrom = (u: User) => save.mutate({ id: u.id, data: { roles: u.roles.filter((r) => r !== selected) } });

  return (
    <div>
      <PageHeader
        icon={ShieldCheck}
        title="Nhóm quyền"
        subtitle="4 vai trò hệ thống cố định (D-07). Gán người dùng vào vai trò; quyền của từng vai trò không sửa từ giao diện."
      />
      <div className={s.layout}>
        <div className={s.roles} role="tablist" aria-label="Vai trò">
          {roles.data?.map((r) => {
            const Icon = ROLE_ICONS[r.name] ?? ShieldCheck;
            return (
              <button
                key={r.name}
                role="tab"
                aria-selected={r.name === selected}
                className={`card ${s.role} ${r.name === selected ? s.active : ""}`}
                onClick={() => setSelected(r.name)}
              >
                <span className={s.roleIcon}>
                  <Icon size={20} aria-hidden />
                </span>
                <span className={s.roleText}>
                  <strong>{ROLE_LABELS[r.name] ?? r.description ?? r.name}</strong>
                  <small>{r.member_count} thành viên</small>
                </span>
              </button>
            );
          })}
        </div>

        {role && (
          <div className="stack">
            <div className="card">
              <h2>{ROLE_LABELS[role.name] ?? role.name}</h2>
              <p className="muted">{role.summary}</p>
              <ul className={s.perms}>
                {role.permissions.map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            </div>

            <div className="card">
              <div className={s.membersHead}>
                <h2>Thành viên ({members.data?.total ?? role.member_count})</h2>
                <button className="btn btn-primary btn-sm" onClick={() => setAdding(true)}>
                  <UserPlus size={15} aria-hidden /> Thêm thành viên
                </button>
              </div>
              <ErrorBox error={save.error} />
              {members.isPending ? (
                <Loading />
              ) : !members.data?.items.length ? (
                <EmptyState icon={UsersRound}>Chưa có thành viên.</EmptyState>
              ) : (
                <table className="table">
                  <thead>
                    <tr>
                      <th>Người dùng</th>
                      <th>Phòng ban</th>
                      <th>Vai trò khác</th>
                      <th>Trạng thái</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {members.data.items.map((u) => {
                      const others = u.roles.filter((r) => r !== selected);
                      const self = u.id === session?.user.id && selected === "ADMIN";
                      const why = self
                        ? "Không thể tự gỡ vai trò Quản trị viên của chính mình"
                        : others.length === 0
                          ? "Mỗi người dùng cần ít nhất một vai trò: gán vai trò khác trước"
                          : undefined;
                      return (
                        <tr key={u.id}>
                          <td>
                            <strong>{u.full_name}</strong>
                            <div className="muted">@{u.username}</div>
                          </td>
                          <td>{depName(u.department_id)}</td>
                          <td>{others.map((r) => ROLE_LABELS[r] ?? r).join(", ") || "—"}</td>
                          <td>{u.is_active ? <Badge tone="ok">Hoạt động</Badge> : <Badge>Đã khóa</Badge>}</td>
                          <td>
                            <div className="row">
                              <Link className="btn btn-sm btn-ghost" to={`/admin/audit?user_id=${u.id}`}>
                                Nhật ký
                              </Link>
                              <button
                                className="btn btn-sm"
                                disabled={Boolean(why) || save.isPending}
                                title={why}
                                onClick={() => removeFrom(u)}
                              >
                                <UserMinus size={15} aria-hidden /> Gỡ
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}
      </div>
      {adding && <AddMember role={selected} onClose={() => setAdding(false)} />}
    </div>
  );
}
