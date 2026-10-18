import { SHARE_MODES, asShareMode } from "./modes";
import s from "./sharing.module.css";

/** Nhãn chế độ chia sẻ (chỉ có ý nghĩa với tài liệu đã xuất bản). compact = chỉ icon, có tooltip/aria-label. */
export function ShareModeBadge({ mode, compact = false }: { mode: string; compact?: boolean }) {
  const info = SHARE_MODES[asShareMode(mode)];
  const Icon = info.icon;
  if (compact) {
    return (
      <span
        className={`${s.modeIcon} ${s[info.tone]}`}
        title={`Chia sẻ: ${info.label}`}
        aria-label={`Chia sẻ: ${info.label}`}
        role="img"
      >
        <Icon size={13} aria-hidden />
      </span>
    );
  }
  return (
    <span className={`${s.modeBadge} ${s[info.tone]}`}>
      <Icon size={13} aria-hidden />
      {info.label}
    </span>
  );
}
