import { Building2, Plus } from "lucide-react";
import { useState, type FormEvent } from "react";

import type { Department } from "@/shared/api/types";
import { EmptyState, ErrorBox, Field, Loading, Modal, PageHeader, fieldErrors } from "@/shared/components/ui";

import { useDeleteDepartment, useDepartments, useSaveDepartment } from "./api";

function DepartmentForm({ department, onClose }: { department: Department | null; onClose: () => void }) {
  const save = useSaveDepartment();
  const errors = fieldErrors(save.error);
  const [code, setCode] = useState(department?.code ?? "");
  const [name, setName] = useState(department?.name ?? "");
  const [description, setDescription] = useState(department?.description ?? "");

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const data = { code: code.trim(), name: name.trim(), description: description.trim() || null };
    save.mutate({ id: department?.id, data }, { onSuccess: onClose });
  };

  return (
    <Modal
      title={department ? `Sửa phòng ban ${department.code}` : "Tạo phòng ban"}
      onClose={onClose}
      actions={
        <button className="btn btn-primary" type="submit" form="dep-form" disabled={save.isPending}>
          Lưu
        </button>
      }
    >
      <form id="dep-form" className="stack" onSubmit={submit}>
        <ErrorBox error={save.error} />
        <Field
          label="Mã"
          htmlFor="dc"
          hint="Duy nhất, tự chuyển chữ in hoa, ví dụ HC-TH"
          error={errors.code ? "Mã phòng ban đã tồn tại" : undefined}
        >
          <input
            id="dc"
            className="input"
            value={code}
            maxLength={50}
            onChange={(e) => setCode(e.target.value)}
            required
          />
        </Field>
        <Field label="Tên" htmlFor="dn">
          <input
            id="dn"
            className="input"
            value={name}
            maxLength={150}
            onChange={(e) => setName(e.target.value)}
            required
          />
        </Field>
        <Field label="Mô tả" htmlFor="dd">
          <textarea
            id="dd"
            className="textarea"
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </Field>
        {department && department.document_count > 0 && (
          <p className="muted">
            Phòng ban là căn cứ phạm vi xem (D-02): đổi tên/mã không ảnh hưởng quyền của {department.document_count} tài
            liệu và {department.user_count} người dùng đang thuộc phòng ban.
          </p>
        )}
      </form>
    </Modal>
  );
}

function DeleteConfirm({ department, onClose }: { department: Department; onClose: () => void }) {
  const remove = useDeleteDepartment();
  return (
    <Modal
      title={`Xóa phòng ban ${department.code}`}
      onClose={onClose}
      actions={
        <button
          className="btn btn-danger"
          disabled={remove.isPending}
          onClick={() => remove.mutate(department.id, { onSuccess: onClose })}
        >
          Xóa
        </button>
      }
    >
      <div className="stack">
        <ErrorBox error={remove.error} />
        <p>
          Xóa vĩnh viễn phòng ban <strong>{department.name}</strong>? Thao tác được ghi nhật ký.
        </p>
      </div>
    </Modal>
  );
}

/** UC-26 (FR-10): chỉ xóa được phòng ban không còn người dùng và tài liệu (409 DEPARTMENT_IN_USE). */
export function DepartmentsPage() {
  const deps = useDepartments();
  const [editing, setEditing] = useState<Department | null | "new">(null);
  const [deleting, setDeleting] = useState<Department | null>(null);

  return (
    <div>
      <PageHeader
        icon={Building2}
        title="Phòng ban"
        subtitle="Căn cứ phạm vi xem tài liệu: người dùng thấy tài liệu thuộc phòng ban của mình"
        actions={
          <button className="btn btn-primary" onClick={() => setEditing("new")}>
            <Plus size={16} aria-hidden /> Tạo phòng ban
          </button>
        }
      />
      <ErrorBox error={deps.error} />
      {deps.isPending ? (
        <Loading />
      ) : !deps.data?.length ? (
        <EmptyState icon={Building2}>Chưa có phòng ban.</EmptyState>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Mã</th>
              <th>Tên</th>
              <th>Mô tả</th>
              <th>Người dùng</th>
              <th>Tài liệu</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {deps.data.map((d) => {
              const inUse = d.user_count > 0 || d.document_count > 0;
              return (
                <tr key={d.id}>
                  <td>{d.code}</td>
                  <td>{d.name}</td>
                  <td className="muted">{d.description ?? "—"}</td>
                  <td>{d.user_count}</td>
                  <td>{d.document_count}</td>
                  <td>
                    <div className="row">
                      <button className="btn btn-sm" onClick={() => setEditing(d)}>
                        Sửa
                      </button>
                      <button
                        className="btn btn-sm"
                        disabled={inUse}
                        title={
                          inUse ? "Còn người dùng hoặc tài liệu (kể cả trong thùng rác), không xóa được" : undefined
                        }
                        onClick={() => setDeleting(d)}
                      >
                        Xóa
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
      {editing && <DepartmentForm department={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
      {deleting && <DeleteConfirm department={deleting} onClose={() => setDeleting(null)} />}
    </div>
  );
}
