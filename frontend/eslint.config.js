// Quy tắc phụ thuộc phía React (Đặc tả đề tài v0.5 mục 4.4, NFR-06):
// - shared/ không import app/ hay features/.
// - feature chỉ import feature khác qua index công khai (không đi sâu vào thư mục nội bộ).
// - feature lõi MVP không import feature P2 (P2 cắm vào bằng slot của UI registry).
import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";
import tseslint from "typescript-eslint";

const P2_FEATURES = [
  "workflow",
  "highlight",
  "handwriting",
  "extraction",
  "classification",
  "versions",
  "borrowing",
  "notifications",
  "imports",
  "rollback",
];
const CORE_FEATURES = ["auth", "documents", "jobs", "ocr", "search", "dashboard", "admin"];

const deepFeatureImport = {
  group: ["@/features/*/*", "!@/features/*/index", "../../features/*/*"],
  message: "Chỉ import feature khác qua index công khai (@/features/<tên>).",
};

export default tseslint.config(
  { ignores: ["dist", "node_modules", "src/shared/api/schema.d.ts"] },
  {
    files: ["**/*.{ts,tsx}"],
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    languageOptions: { ecmaVersion: 2022, globals: globals.browser },
    plugins: { "react-hooks": reactHooks, "react-refresh": reactRefresh },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
    },
  },
  {
    files: ["src/shared/**/*.{ts,tsx}"],
    rules: {
      "react-refresh/only-export-components": "off", // context/hook/tiện ích dùng chung, không phải trang
      "no-restricted-imports": [
        "error",
        { patterns: [{ group: ["@/app/*", "@/features/*"], message: "shared/ không phụ thuộc app/ hay features/." }] },
      ],
    },
  },
  ...CORE_FEATURES.map((name) => ({
    files: [`src/features/${name}/**/*.{ts,tsx}`],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            { ...deepFeatureImport, group: [...deepFeatureImport.group, `!@/features/${name}/**`] },
            {
              group: P2_FEATURES.map((p) => `@/features/${p}`).concat(P2_FEATURES.map((p) => `@/features/${p}/*`)),
              message: "R9: feature lõi MVP không import feature P2 (dùng slot của UI registry).",
            },
            { group: ["@/app/*"], message: "feature không import app/ (app import feature)." },
          ],
        },
      ],
    },
  })),
  ...P2_FEATURES.map((name) => ({
    files: [`src/features/${name}/**/*.{ts,tsx}`],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            { ...deepFeatureImport, group: [...deepFeatureImport.group, `!@/features/${name}/**`] },
            { group: ["@/app/*"], message: "feature không import app/ (app import feature)." },
          ],
        },
      ],
    },
  })),
);
