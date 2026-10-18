import { Search, UserPlus } from "lucide-react";
import { useId, useState, type KeyboardEvent } from "react";

import type { UserLookup } from "@/shared/api/types";
import { Spinner } from "@/shared/components/ui";
import { useDebounce } from "@/shared/hooks/useDebounce";

import { useUserLookup } from "../api";
import { Avatar } from "./Avatar";
import s from "./sharing.module.css";

/**
 * Ô tìm người dùng để chia sẻ (ARIA combobox): gõ ≥ 2 ký tự, ↑/↓ chọn, Enter thêm, Esc đóng.
 * Người đã được thêm (excludeIds) không hiện lại trong gợi ý.
 */
export function PeoplePicker({ excludeIds, onAdd }: { excludeIds: Set<string>; onAdd: (user: UserLookup) => void }) {
  const listId = useId();
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const term = useDebounce(q, 250);
  const lookup = useUserLookup(term);
  const ready = q.trim().length >= 2;
  const options = ready ? (lookup.data ?? []).filter((u) => !excludeIds.has(u.id)) : [];
  const showList = open && ready;

  const add = (user: UserLookup) => {
    onAdd(user);
    setQ("");
    setActive(0);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown" && options.length) {
      e.preventDefault();
      setOpen(true);
      setActive((i) => (i + 1) % options.length);
    } else if (e.key === "ArrowUp" && options.length) {
      e.preventDefault();
      setActive((i) => (i - 1 + options.length) % options.length);
    } else if (e.key === "Enter" && showList && options[active]) {
      e.preventDefault();
      add(options[active]);
    } else if (e.key === "Escape" && showList) {
      e.stopPropagation(); // Esc đầu tiên chỉ đóng gợi ý, không đóng hộp thoại
      setOpen(false);
    }
  };

  return (
    <div className={s.picker}>
      <div className={s.pickerField}>
        <Search size={16} className={s.pickerIcon} aria-hidden />
        <input
          className="input"
          role="combobox"
          aria-expanded={showList}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={showList && options[active] ? `${listId}-${options[active].id}` : undefined}
          aria-label="Thêm người theo tên, tên đăng nhập hoặc email"
          placeholder="Tìm và thêm người…"
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setOpen(true);
            setActive(0);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setOpen(false)}
          onKeyDown={onKeyDown}
        />
        {lookup.isFetching && ready && (
          <span className={s.pickerSpin}>
            <Spinner label="Đang tìm" />
          </span>
        )}
      </div>
      {showList && (
        <ul className={s.options} id={listId} role="listbox" aria-label="Người dùng phù hợp">
          {options.length === 0 ? (
            <li className={s.noOption} role="presentation">
              {lookup.isFetching || term !== q ? "Đang tìm…" : "Không tìm thấy người dùng phù hợp"}
            </li>
          ) : (
            options.map((u, i) => (
              <li
                key={u.id}
                id={`${listId}-${u.id}`}
                role="option"
                aria-selected={i === active}
                className={`${s.option} ${i === active ? s.optionActive : ""}`}
                onMouseEnter={() => setActive(i)}
                // mousedown thay vì click: chạy trước blur của input nên danh sách chưa bị đóng
                onMouseDown={(e) => {
                  e.preventDefault();
                  add(u);
                }}
              >
                <Avatar name={u.full_name} />
                <span className={s.personText}>
                  <strong>{u.full_name}</strong>
                  <small>
                    @{u.username}
                    {u.department_name ? ` · ${u.department_name}` : ""}
                  </small>
                </span>
                <UserPlus size={16} className={s.optionAdd} aria-hidden />
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}
