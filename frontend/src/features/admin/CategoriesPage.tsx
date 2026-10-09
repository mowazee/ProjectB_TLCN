import { useState, type FormEvent } from "react";

import type { Category } from "@/shared/api/types";
import { Badge, ErrorBox, Field, Loading, Modal, PageHeader, fieldErrors } from "@/shared/components/ui";
import { useCategories } from "@/shared/hooks/useCategories";

import { useSaveCategory } from "./api";

function CategoryForm({ category, all, onClose }: { category: Category | null; all: Category[]; onClose: () => void }) {
  const save = useSaveCategory();
  const errors = fieldErrors(save.error);
  const [name, setName] = useState(category?.name ?? "");
  const [code, setCode] = useState(category?.code ?? "");
  const [parent, setParent] = useState(category?.parent_id ? String(category.parent_id) : "");
  const [years, setYears] = useState(category?.retention_period_years ? String(category.retention_period_years) : "");
  const [description, setDescription] = useState(category?.description ?? "");

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const data = {
      name: name.trim(),
      parent_id: parent ? Number(parent) : null,
      retention_period_years: years ? Number(years) : null,
      description: description.trim() || null,
    };
    save.mutate({ id: category?.id, data: category ? data : { ...data, code: code.trim() } }, { onSuccess: onClose });
  };

  return (
    <Modal
      title={category ? `Sửa danh mục ${category.code}` : "Tạo danh mục"}
      onClose={onClose}
      actions={
        <button className="btn btn-primary" type="submit" form="cat-form" disabled={save.isPending}>
          Lưu
        </button>
      }
    >
      <form id="cat-form" className="stack" onSubmit={submit}>
        <ErrorBox error={save.error} />
        <Field label="Tên" htmlFor="n" error={errors.name}>
          <input id="n" className="input" value={name} onChange={(e) => setName(e.target.value)} required />
        </Field>
        {!category && (
          <Field label="Mã" htmlFor="c" hint="Chữ in hoa, không dấu, ví dụ HOP-DONG" error={errors.code}>
            <input id="c" className="input" value={code} onChange={(e) => setCode(e.target.value)} required />
          </Field>
        )}
        <Field label="Danh mục cha" htmlFor="p" error={errors.parent_id}>
          <select id="p" className="select" value={parent} onChange={(e) => setParent(e.target.value)}>
            <option value="">— Không —</option>
            {all
              .filter((c) => c.id !== category?.id)
              .map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
          </select>
        </Field>
        <Field label="Thời hạn lưu trữ (năm)" htmlFor="y" error={errors.retention_period_years}>
          <input
            id="y"
            className="input"
            type="number"
            min={0}
            value={years}
            onChange={(e) => setYears(e.target.value)}
          />
        </Field>
        <Field label="Mô tả" htmlFor="d" hint="Từ khóa mô tả giúp gợi ý phân loại (P2-05)">
          <textarea
            id="d"
            className="textarea"
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </Field>
      </form>
    </Modal>
  );
}

/** UC-09 (FR-02): ngừng sử dụng thay vì xóa; danh mục ngừng dùng không chọn được cho tài liệu mới. */
export function CategoriesPage() {
  const categories = useCategories();
  const save = useSaveCategory();
  const [editing, setEditing] = useState<Category | null | "new">(null);
  const all = categories.data ?? [];

  return (
    <div>
      <PageHeader
        title="Danh mục tài liệu"
        actions={
          <button className="btn btn-primary" onClick={() => setEditing("new")}>
            + Tạo danh mục
          </button>
        }
      />
      <ErrorBox error={categories.error ?? save.error} />
      {categories.isPending ? (
        <Loading />
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Mã</th>
              <th>Tên</th>
              <th>Danh mục cha</th>
              <th>Lưu trữ</th>
              <th>Trạng thái</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {all.map((c) => (
              <tr key={c.id}>
                <td>{c.code}</td>
                <td>{c.name}</td>
                <td>{all.find((p) => p.id === c.parent_id)?.name ?? "—"}</td>
                <td>{c.retention_period_years ? `${c.retention_period_years} năm` : "—"}</td>
                <td>{c.is_active ? <Badge tone="ok">Đang dùng</Badge> : <Badge>Ngừng dùng</Badge>}</td>
                <td className="row">
                  <button className="btn btn-sm" onClick={() => setEditing(c)}>
                    Sửa
                  </button>
                  <button
                    className="btn btn-sm"
                    disabled={save.isPending}
                    onClick={() => save.mutate({ id: c.id, data: { is_active: !c.is_active } })}
                  >
                    {c.is_active ? "Ngừng dùng" : "Dùng lại"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {editing && (
        <CategoryForm category={editing === "new" ? null : editing} all={all} onClose={() => setEditing(null)} />
      )}
    </div>
  );
}
