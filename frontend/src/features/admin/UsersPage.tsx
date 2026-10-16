import { Users } from "lucide-react";
import { useState, type FormEvent } from "react";

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

import { useDepartments, useRoles, useSaveUser, useUsers } from "./api";

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
        <Field label={user ? "Mật khẩu mới (để trống nếu không đổi)" : "Mật khẩu"} htmlFor="pw" error={errors.password}>
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
      </form>
    </Modal>
  );
}

/** UC-06 (FR-01): Admin tạo, sửa, khóa người dùng và gán vai trò. */
export function UsersPage() {
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const query = useDebounce(q);
  const users = useUsers(page, query);
  const [editing, setEditing] = useState<User | null | "new">(null);

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
      <input
        className="input"
        placeholder="Tìm theo tên đăng nhập, họ tên, email..."
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setPage(1);
        }}
        style={{ marginBottom: 12 }}
      />
      <ErrorBox error={users.error} />
      {users.isPending ? (
        <Loading />
      ) : !users.data?.items.length ? (
        <EmptyState>Không có người dùng.</EmptyState>
      ) : (
        <>
          <table className="table">
            <thead>
              <tr>
                <th>Tên đăng nhập</th>
                <th>Họ tên</th>
                <th>Email</th>
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
                  <td>{u.roles.map((r) => ROLE_LABELS[r] ?? r).join(", ")}</td>
                  <td>{u.is_active ? <Badge tone="ok">Hoạt động</Badge> : <Badge tone="danger">Đã khóa</Badge>}</td>
                  <td>{formatDateTime(u.last_login_at)}</td>
                  <td>
                    <button className="btn btn-sm" onClick={() => setEditing(u)}>
                      Sửa
                    </button>
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
