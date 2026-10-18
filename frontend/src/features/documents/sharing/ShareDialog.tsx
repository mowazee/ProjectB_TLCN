import { Check, Info, Lock, UsersRound, X } from "lucide-react";
import { useState } from "react";

import type { DocumentOut, ShareUser, Sharing, UserLookup } from "@/shared/api/types";
import { ErrorBox, Loading, Modal } from "@/shared/components/ui";

import { useDepartmentOptions, useSaveSharing, useSharing } from "../api";
import { Avatar } from "./Avatar";
import { SHARE_MODES, SHARE_MODE_ORDER, asShareMode, type ShareMode } from "./modes";
import { PeoplePicker } from "./PeoplePicker";
import s from "./sharing.module.css";

type Person = Pick<ShareUser, "id" | "username" | "full_name" | "department_name">;

function describe(mode: ShareMode, ownerDept: string): string {
  if (mode === "private") return `Chỉ bạn, quản trị viên, kiểm duyệt viên ${ownerDept} và những người được thêm.`;
  if (mode === "internal") return `Mọi người thuộc ${ownerDept} và các phòng ban bạn chọn thêm.`;
  return "Mọi người dùng đã đăng nhập đều xem, tìm kiếm và tải được.";
}

function summary(mode: ShareMode, ownerDept: string, deps: number, people: number): string {
  if (mode === "public") return "Mọi người dùng trong hệ thống có quyền xem";
  const parts = mode === "internal" ? [ownerDept] : ["Chỉ bạn"];
  if (mode === "internal" && deps > 0) parts.push(`${deps} phòng ban khác`);
  if (people > 0) parts.push(`${people} người được thêm`);
  return `${parts.join(", ")} có quyền xem`;
}

/** Biểu mẫu chỉ dựng khi đã có cấu hình từ server: state khởi tạo một lần từ dữ liệu đó. */
function ShareForm({ doc, sharing, onClose }: { doc: DocumentOut; sharing: Sharing; onClose: () => void }) {
  const save = useSaveSharing(doc.id);
  const departments = useDepartmentOptions(true);
  const [mode, setMode] = useState<ShareMode>(asShareMode(sharing.share_mode));
  const [deps, setDeps] = useState<Set<number>>(() => new Set(sharing.departments.map((d) => d.id)));
  const [people, setPeople] = useState<Person[]>(sharing.users);
  const ownerDept = sharing.owner_department?.name ?? "phòng ban của tài liệu";
  const others = (departments.data ?? []).filter((d) => d.id !== sharing.owner_department?.id);
  // Ở chế độ Nội bộ, người thuộc phòng ban đã được chia sẻ vốn có quyền: ghi rõ để người dùng không thêm thừa
  const coveredDepts = new Set(
    mode === "internal" ? [ownerDept, ...others.filter((d) => deps.has(d.id)).map((d) => d.name)] : [],
  );

  const initialDeps = sharing.departments.map((d) => d.id).sort();
  const initialPeople = sharing.users.map((u) => u.id).sort();
  const dirty =
    mode !== asShareMode(sharing.share_mode) ||
    JSON.stringify([...deps].sort()) !== JSON.stringify(initialDeps) ||
    JSON.stringify(people.map((p) => p.id).sort()) !== JSON.stringify(initialPeople);

  const toggleDep = (id: number) =>
    setDeps((cur) => {
      const next = new Set(cur);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  const addPerson = (u: UserLookup) => setPeople((cur) => (cur.some((p) => p.id === u.id) ? cur : [...cur, u]));
  const removePerson = (id: string) => setPeople((cur) => cur.filter((p) => p.id !== id));

  const submit = () =>
    save.mutate(
      {
        share_mode: mode,
        department_ids: mode === "internal" ? [...deps] : [],
        user_ids: people.map((p) => p.id),
      },
      { onSuccess: onClose },
    );

  return (
    <Modal
      title={`Chia sẻ "${doc.title}"`}
      size="lg"
      onClose={onClose}
      closeLabel="Hủy"
      aside={
        <span className={s.summary}>
          <UsersRound size={16} aria-hidden />
          {summary(mode, ownerDept, mode === "internal" ? deps.size : 0, mode === "public" ? 0 : people.length)}
        </span>
      }
      actions={
        <button className="btn btn-primary" onClick={submit} disabled={!dirty || save.isPending}>
          {save.isPending ? "Đang lưu…" : "Lưu thay đổi"}
        </button>
      }
    >
      <div className={s.form}>
        <ErrorBox error={save.error} />
        <section aria-labelledby="share-access">
          <h3 className={s.sectionTitle} id="share-access">
            Quyền truy cập chung
          </h3>
          <div className={s.modes} role="radiogroup" aria-labelledby="share-access">
            {SHARE_MODE_ORDER.map((m) => {
              const info = SHARE_MODES[m];
              const Icon = info.icon;
              const selected = m === mode;
              return (
                <button
                  key={m}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  className={`${s.mode} ${selected ? s.modeSelected : ""}`}
                  onClick={() => setMode(m)}
                >
                  <span className={`${s.modeTile} ${s[info.tone]}`}>
                    <Icon size={18} aria-hidden />
                  </span>
                  <span className={s.modeText}>
                    <strong>{info.label}</strong>
                    <small>{describe(m, ownerDept)}</small>
                  </span>
                  <span className={s.modeCheck} aria-hidden>
                    {selected && <Check size={14} />}
                  </span>
                </button>
              );
            })}
          </div>
        </section>

        {mode === "internal" && (
          <section aria-labelledby="share-deps">
            <h3 className={s.sectionTitle} id="share-deps">
              Phòng ban được chia sẻ
            </h3>
            <div className={s.chips}>
              <span
                className={`${s.chip} ${s.chipLocked}`}
                title="Phòng ban của tài liệu luôn có quyền ở chế độ Nội bộ"
              >
                <Lock size={13} aria-hidden /> {ownerDept}
              </span>
              {others.map((d) => {
                const on = deps.has(d.id);
                return (
                  <button
                    key={d.id}
                    type="button"
                    role="checkbox"
                    aria-checked={on}
                    className={`${s.chip} ${on ? s.chipOn : ""}`}
                    onClick={() => toggleDep(d.id)}
                  >
                    {on && <Check size={13} aria-hidden />}
                    {d.name}
                  </button>
                );
              })}
            </div>
            {departments.isSuccess && others.length === 0 && (
              <p className={s.hint}>Hệ thống chưa có phòng ban nào khác.</p>
            )}
          </section>
        )}

        {mode === "public" ? (
          <p className={s.note}>
            <Info size={16} aria-hidden />Ở chế độ Toàn hệ thống không cần thêm từng người. Danh sách người đã thêm được
            giữ lại nếu bạn đổi về chế độ khác.
          </p>
        ) : (
          <section aria-labelledby="share-people">
            <h3 className={s.sectionTitle} id="share-people">
              Người được chia sẻ
            </h3>
            <PeoplePicker excludeIds={new Set(people.map((p) => p.id))} onAdd={addPerson} />
            {people.length === 0 ? (
              <p className={s.hint}>Chưa thêm ai. Người được thêm sẽ nhận thông báo.</p>
            ) : (
              <ul className={s.people} aria-label="Người được chia sẻ">
                {people.map((p) => (
                  <li key={p.id} className={s.person}>
                    <Avatar name={p.full_name} />
                    <span className={s.personText}>
                      <strong>{p.full_name}</strong>
                      <small>
                        @{p.username}
                        {p.department_name ? ` · ${p.department_name}` : ""}
                      </small>
                    </span>
                    <span className={s.access}>
                      {p.department_name && coveredDepts.has(p.department_name)
                        ? "Đã có quyền qua phòng ban"
                        : "Xem, tải"}
                    </span>
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm btn-icon"
                      onClick={() => removePerson(p.id)}
                      aria-label={`Gỡ ${p.full_name}`}
                      title="Gỡ quyền"
                    >
                      <X size={16} aria-hidden />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}

        <p className={s.note}>
          <Info size={16} aria-hidden />
          Chia sẻ chỉ cho phép xem, tìm kiếm, tải và yêu cầu mượn hồ sơ. Người được chia sẻ không sửa, xóa hay duyệt tài
          liệu.
        </p>
      </div>
    </Modal>
  );
}

/** UC-29 (FR-13): hộp thoại chia sẻ cho chủ sở hữu/Admin - chỉ mở khi tài liệu đã xuất bản. */
export function ShareDialog({ doc, onClose }: { doc: DocumentOut; onClose: () => void }) {
  const sharing = useSharing(doc.id, true);
  if (!sharing.data) {
    return (
      <Modal title={`Chia sẻ "${doc.title}"`} size="lg" onClose={onClose}>
        {sharing.error ? <ErrorBox error={sharing.error} /> : <Loading />}
      </Modal>
    );
  }
  return <ShareForm doc={doc} sharing={sharing.data} onClose={onClose} />;
}
