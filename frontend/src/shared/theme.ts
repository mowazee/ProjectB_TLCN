/**
 * Giao diện sáng/tối. Lựa chọn của người dùng lưu ở localStorage (chỉ là tiện ích, có thể bị chặn);
 * "system" theo prefers-color-scheme của hệ điều hành. Giá trị áp dụng nằm ở <html data-theme="light|dark">,
 * CSS chỉ đọc thuộc tính đó. public/theme-init.js đặt giá trị ban đầu trước khi React chạy.
 */
import { useSyncExternalStore } from "react";

export type ThemePreference = "system" | "light" | "dark";
export type Theme = "light" | "dark";

const KEY = "theme";
// matchMedia có thể không có (jsdom khi test) -> coi như hệ điều hành dùng nền sáng
const media = (): MediaQueryList | undefined => window.matchMedia?.("(prefers-color-scheme: dark)");
const listeners = new Set<() => void>();

function readPreference(): ThemePreference {
  try {
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : "system";
  } catch {
    return "system";
  }
}

let preference: ThemePreference = typeof window === "undefined" ? "system" : readPreference();

function resolve(pref: ThemePreference): Theme {
  if (pref !== "system") return pref;
  return typeof window !== "undefined" && media()?.matches ? "dark" : "light";
}

function apply() {
  document.documentElement.dataset.theme = resolve(preference);
  listeners.forEach((l) => l());
}

export function setThemePreference(pref: ThemePreference) {
  preference = pref;
  try {
    if (pref === "system") localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, pref);
  } catch {
    /* không lưu được thì chỉ áp dụng trong phiên này */
  }
  apply();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  const mq = media();
  const onChange = () => preference === "system" && apply();
  mq?.addEventListener("change", onChange);
  return () => {
    listeners.delete(listener);
    mq?.removeEventListener("change", onChange);
  };
}

const snapshot = () => `${preference}|${resolve(preference)}`;

/** { preference, theme }: theme là giá trị đang áp dụng (đã giải "system"). */
export function useTheme(): { preference: ThemePreference; theme: Theme } {
  const [pref, theme] = useSyncExternalStore(subscribe, snapshot, () => "system|light").split("|");
  return { preference: pref as ThemePreference, theme: theme as Theme };
}

/** Đọc một biến CSS đang áp dụng (dùng cho Chart.js, vốn không đọc được var(--x)). */
export function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}
