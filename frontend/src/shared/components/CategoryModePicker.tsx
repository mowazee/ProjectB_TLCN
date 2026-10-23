import { Check, FolderTree, Sparkles, type LucideIcon } from "lucide-react";

import s from "./CategoryModePicker.module.css";

export type CategoryMode = "auto" | "user";

const MODES: { mode: CategoryMode; icon: LucideIcon; tone: "violet" | "slate"; label: string; hint: string }[] = [
  {
    mode: "auto",
    icon: Sparkles,
    tone: "violet",
    label: "Danh mục gợi ý",
    hint: "Hệ thống tự chọn danh mục sau khi OCR xong. Nếu chưa đủ chắc chắn, tài liệu nằm ở “Chưa phân loại” và bạn được thông báo để tự chọn.",
  },
  {
    mode: "user",
    icon: FolderTree,
    tone: "slate",
    label: "Tôi chọn danh mục",
    hint: "Chọn ngay một danh mục cho tài liệu.",
  },
];

/** D-10: chọn cách gán danh mục (tải lên một file, nhập hàng loạt) - thẻ chọn kiểu radio, mặc định Danh mục gợi ý.
 *  hints: thay mô tả mặc định của từng thẻ (vd. nói về "mỗi file trong lô"). */
export function CategoryModePicker({
  value,
  onChange,
  hints,
}: {
  value: CategoryMode;
  onChange: (m: CategoryMode) => void;
  hints?: Partial<Record<CategoryMode, string>>;
}) {
  return (
    <div className={s.catModes} role="radiogroup" aria-label="Cách chọn danh mục">
      {MODES.map(({ mode, icon: Icon, tone, label, hint }) => {
        const selected = mode === value;
        return (
          <button
            key={mode}
            type="button"
            role="radio"
            aria-checked={selected}
            className={`${s.catMode} ${selected ? s.catModeSelected : ""}`}
            onClick={() => onChange(mode)}
          >
            <span className={`${s.catModeTile} ${s[tone]}`}>
              <Icon size={18} aria-hidden />
            </span>
            <span className={s.catModeText}>
              <strong>
                {label}
                {mode === "auto" && <span className={s.catModeTag}>Mặc định</span>}
              </strong>
              <small>{hints?.[mode] ?? hint}</small>
            </span>
            <span className={s.catModeCheck} aria-hidden>
              {selected && <Check size={14} />}
            </span>
          </button>
        );
      })}
    </div>
  );
}
