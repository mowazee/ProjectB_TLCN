/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Cấu hình công khai (SDD mục 14: mọi VITE_* là public, không chứa secret). */
  readonly VITE_JOB_POLL_MS?: string;
  readonly VITE_MAX_UPLOAD_MB?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
