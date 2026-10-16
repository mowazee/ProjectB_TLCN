import { Monitor, Moon, Sun } from "lucide-react";

import { setThemePreference, useTheme, type ThemePreference } from "@/shared/theme";

const NEXT: Record<ThemePreference, ThemePreference> = { system: "light", light: "dark", dark: "system" };
const LABEL: Record<ThemePreference, string> = { system: "Theo hệ thống", light: "Sáng", dark: "Tối" };
const ICON = { system: Monitor, light: Sun, dark: Moon };

/** Nút đổi giao diện: Theo hệ thống -> Sáng -> Tối. Icon cho biết lựa chọn hiện tại. */
export function ThemeToggle({ className = "" }: { className?: string }) {
  const { preference } = useTheme();
  const Icon = ICON[preference];
  const label = `Giao diện: ${LABEL[preference]} (bấm để chuyển sang ${LABEL[NEXT[preference]]})`;
  return (
    <button
      type="button"
      className={`btn btn-ghost btn-icon ${className}`}
      onClick={() => setThemePreference(NEXT[preference])}
      aria-label={label}
      title={label}
    >
      <Icon size={19} aria-hidden />
    </button>
  );
}
