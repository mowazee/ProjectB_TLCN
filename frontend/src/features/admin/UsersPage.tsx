import { LogOut, Users } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link } from "react-router";

import type { User } from "@/shared/api/types";
import {
  Badge,
  EmptyState,
  ErrorBox,
  Field,
  Loading,
  Modal,
  PageHeader,
  Pagination,
  fieldErrors,
} from "@/shared/components/ui";
import { useDebounce } from "@/shared/hooks/useDebounce";
import { ROLE_LABELS, formatDateTime } from "@/shared/lib/format";

import { useDepartments, useRevokeSessions, useRoles, useSaveUser, useUsers, type UserFilters } from "./api";

/** FR-01 (v0.7): buộc đăng xuất mọi thiết bị (nghi lộ mật khẩu, máy dùng chung...). */
function RevokeSessions({ user }: { user: User }) {
  const revoke = useRevokeSessions();
  return (
    <div className="stack" style={{ gap: 8 }}>
      <ErrorBox error={revoke.error} />
      <div className="row">
        <button type="button" className="btn btn-sm" disabled={revoke.isPending} onClick={() => revoke.mutate(user.id)}>
          <LogOut size={15} aria-hidden /> Đăng xuất khỏi mọi thiết bị
        </button>
        {revoke.data && <span className="muted">Đã thu hồi {revoke.data.revoked} phiên đăng nhập.</span>}
      </div>
    </div>
  );
}

function UserForm({ user, onClose }: { user: User | null; onClose: () => void }) {
  const roles = useRoles();
  const deps = useDepartments();
  const save = useSaveUser();
  const errors = fieldErrors(save.error);
  const [form, setForm] = useState({
    username: user?.username ?? "",
    email: user?.email ?? "",
    full_name: user?.full_name ?? "",
    phone: user?.phone ?? "",
    password: "",
    department_id: user?.department_id ? String(user.department_id) : "",
    roles: user?.roles ?? ["OFFICER"],
    is_active: user?.is_active ?? true,
  });
  const set = (k: keyof typeof form, v: unknown) => setForm((f) => ({ ...f, [k]: v }));

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const common = {
      email: form.email.trim(),
      full_name: form.full_name.trim(),
      phone: form.phone.trim() || null,
      department_id: form.department_id ? Number(form.department_id) : null,
      roles: form.roles,
    };
    const data = user
      ? { ...common, is_active: form.is_active, ...(form.password ? { password: form.password } : {}) }
      : { ...common, username: form.username.trim(), password: form.password };
    save.mutate({ id: user?.id, data }, { onSuccess: onClose });
  };

  return (
    <Modal
      title={user ? `Sửa người dùng ${user.username}` : "Tạo người dùng"}
      onClose={onClose}
      actions={
        <button className="btn btn-primary" type="submit" form="user-form" disabled={save.isPending}>
          Lưu
        </button>
      }
    >
      <form id="user-form" className="stack" onSubmit={submit}>
        <ErrorBox error={save.error} />
        {!user && (
          <Field label="Tên đăng nhập" htmlFor="u" error={errors.username}>
            <input
              id="u"
              className="input"
              value={form.username}
              onChange={(e) => set("username", e.target.value)}
              required
            />
          </Field>
        )}
        <Field label="Họ tên" htmlFor="fn" error={errors.full_name}>
          <input
            id="fn"
            className="input"
            value={form.full_name}
            onChange={(e) => set("full_name", e.target.value)}
            required
          />
        </Field>
        <Field label="Email" htmlFor="em" error={errors.email}>
          <input
            id="em"
            className="input"
            type="email"
            value={form.email}
            onChange={(e) => set("email", e.target.value)}
            required
          />
        </Field>
        <Field label="Điện thoại" htmlFor="ph" error={errors.phone}>
          <input id="ph" className="input" value={form.phone} onChange={(e) => set("phone", e.target.value)} />
        </Field>
        <Field
          label={user ? "Đặt lại mật khẩu (để trống nếu không đổi)" : "Mật khẩu"}
          htmlFor="pw"
          hint={user ? "Người dùng sẽ bị đăng xuất khỏi mọi thiết bị và đăng nhập lại bằng mật khẩu mới" : undefined}
          error={errors.password}
        >
          <input
            id="pw"
            className="input"
            type="password"
            autoComplete="new-password"
            value={form.password}
            onChange={(e) => set("password", e.target.value)}
            required={!user}
          />
        </Field>
        <Field label="Phòng ban" htmlFor="dep" error={errors.department_id}>
          <select
            id="dep"
            className="select"
            value={form.department_id}
            onChange={(e) => set("department_id", e.target.value)}
          >
            <option value="">— Không —</option>
            {deps.data?.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Vai trò" error={errors.roles}>
          <div className="row">
            {roles.data?.map((r) => (
              <label key={r.id} className="row">
                <input
                  type="checkbox"
                  checked={form.roles.includes(r.name)}
                  onChange={(e) =>
                    set("roles", e.target.checked ? [...form.roles, r.name] : form.roles.filter((x) => x !== r.name))
                  }
                />
                {ROLE_LABELS[r.name] ?? r.name}
              </label>
            ))}
          </div>
        </Field>
        {user && (
          <label className="row">
            <input type="checkbox" checked={form.is_active} onChange={(e) => set("is_active", e.target.checked)} />
            Đang hoạt động (bỏ chọn để khóa tài khoản và thu hồi phiên đăng nhập)
          </label>
        )}
        {user && <RevokeSessions user={user} />}
      </form>
    </Modal>
  );
}

const NO_FILTERS: UserFilters = { q: "", role: "", department_id: "", is_active: "" };

/** UC-06 (FR-01): Admin tạo, sửa, khóa người dùng, gán vai trò; lọc theo vai trò/phòng ban/trạng thái (v0.7). */
export function UsersPage() {
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState(NO_FILTERS);
  const q = useDebounce(filters.q);
  const users = useUsers(page, { ...filters, q });
  const roles = useRoles();
  const deps = useDepartments();
  const depName = new Map(deps.data?.map((d) => [d.id, d.name]));
  const [editing, setEditing] = useState<User | null | "new">(null);
  const set = (k: keyof UserFilters, v: string) => {
    setFilters((f) => ({ ...f, [k]: v }));
    setPage(1);
  };
  const filtered = Object.values(filters).some(Boolean);

  return (
    <div>
      <PageHeader
        icon={Users}
        title="Người dùng"
        actions={
          <button className="btn btn-primary" onClick={() => setEditing("new")}>
            + Tạo người dùng
          </button>
        }
      />
      <div className="row" style={{ marginBottom: 12 }}>
        <input
          className="input grow"
          style={{ minWidth: 220 }}
          placeholder="Tìm theo tên đăng nhập, họ tên, email..."
          aria-label="Tìm người dùng"
          value={filters.q}
          onChange={(e) => set("q", e.target.value)}
        />
        <select
          className="select"
          style={{ width: "auto" }}
          aria-label="Lọc theo vai trò"
          value={filters.role}
          onChange={(e) => set("role", e.target.value)}
        >
          <option value="">Mọi vai trò</option>
          {roles.data?.map((r) => (
            <option key={r.id} value={r.name}>
              {ROLE_LABELS[r.name] ?? r.name}
            </option>
          ))}
        </select>
        <select
          className="select"
          style={{ width: "auto" }}
          aria-label="Lọc theo phòng ban"
          value={filters.department_id}
          onChange={(e) => set("department_id", e.target.value)}
        >
          <option value="">Mọi phòng ban</option>
          {deps.data?.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </select>
        <select
          className="select"
          style={{ width: "auto" }}
          aria-label="Lọc theo trạng thái"
          value={filters.is_active}
          onChange={(e) => set("is_active", e.target.value)}
        >
          <option value="">Mọi trạng thái</option>
          <option value="true">Hoạt động</option>
          <option value="false">Đã khóa</option>
        </select>
        {filtered && (
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => {
              setFilters(NO_FILTERS);
              setPage(1);
            }}
          >
            Xóa bộ lọc
          </button>
        )}
      </div>
      <ErrorBox error={users.error} />
      {users.isPending ? (
        <Loading />
      ) : !users.data?.items.length ? (
        <EmptyState>{filtered ? "Không có người dùng khớp bộ lọc." : "Không có người dùng."}</EmptyState>
      ) : (
        <>
          <table className="table">
            <thead>
              <tr>
                <th>Tên đăng nhập</th>
                <th>Họ tên</th>
                <th>Email</th>
                <th>Phòng ban</th>
                <th>Vai trò</th>
                <th>Trạng thái</th>
                <th>Đăng nhập gần nhất</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {users.data.items.map((u) => (
                <tr key={u.id}>
                  <td>{u.username}</td>
                  <td>{u.full_name}</td>
                  <td>{u.email}</td>
                  <td>{u.department_id ? (depName.get(u.department_id) ?? "—") : "—"}</td>
                  <td>{u.roles.map((r) => ROLE_LABELS[r] ?? r).join(", ")}</td>
                  <td>{u.is_active ? <Badge tone="ok">Hoạt động</Badge> : <Badge tone="danger">Đã khóa</Badge>}</td>
                  <td>{formatDateTime(u.last_login_at)}</td>
                  <td>
                    <div className="row" style={{ flexWrap: "nowrap" }}>
                      <button className="btn btn-sm" onClick={() => setEditing(u)}>
                        Sửa
                      </button>
                      {/* FR-01 (v0.7): mở nhanh nhật ký thao tác của người này */}
                      <Link className="btn btn-sm" to={`/admin/audit?user_id=${u.id}`}>
                        Nhật ký
                      </Link>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <Pagination page={page} pageSize={users.data.page_size} total={users.data.total} onChange={setPage} />
        </>
      )}
      {editing && <UserForm user={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
    </div>
  );
}
