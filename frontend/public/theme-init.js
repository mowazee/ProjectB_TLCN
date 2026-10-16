// Đặt giao diện sáng/tối TRƯỚC khi React chạy để không nháy nền trắng.
// File tĩnh riêng (không inline) vì CSP của Nginx chỉ cho script-src 'self'.
// Đồng bộ với src/shared/theme.ts (khóa "theme": "light" | "dark" | "system").
(function () {
  var pref = "system";
  try {
    pref = localStorage.getItem("theme") || "system";
  } catch (e) {
    /* localStorage bị chặn: theo hệ điều hành */
  }
  var dark = pref === "dark" || (pref !== "light" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
})();
