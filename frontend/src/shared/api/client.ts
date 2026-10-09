/**
 * API client duy nhất (SDD mục 13, 14): fetch + credentials "include" + header X-CSRF-Token cho thao tác ghi,
 * chuẩn lỗi {error:{code,message,fields?,request_id}} -> ApiError. FormData không tự đặt Content-Type.
 * 401 phát sự kiện để AuthProvider chuyển về /login (giữ route dự định).
 */

export interface ErrorEnvelope {
  error: {
    code: string;
    message: string;
    fields?: Record<string, string>;
    details?: Record<string, unknown>;
    request_id?: string | null;
  };
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly fields?: Record<string, string>;
  readonly details?: Record<string, unknown>;
  readonly requestId?: string | null;

  constructor(status: number, body: Partial<ErrorEnvelope["error"]> | undefined) {
    super(body?.message || `Lỗi ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.code = body?.code || `HTTP_${status}`;
    this.fields = body?.fields;
    this.details = body?.details;
    this.requestId = body?.request_id;
  }
}

const UNSAFE = new Set(["POST", "PUT", "PATCH", "DELETE"]);
let csrfToken: string | null = null;
const unauthorizedListeners = new Set<() => void>();

export function setCsrfToken(token: string | null): void {
  csrfToken = token;
}

export function onUnauthorized(fn: () => void): () => void {
  unauthorizedListeners.add(fn);
  return () => unauthorizedListeners.delete(fn);
}

export type Query = Record<string, string | number | boolean | null | undefined>;

export function withQuery(path: string, query?: Query): string {
  if (!query) return path;
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) {
    if (v !== undefined && v !== null && v !== "") params.set(k, String(v));
  }
  const qs = params.toString();
  return qs ? `${path}?${qs}` : path;
}

export interface RequestOptions {
  method?: string;
  query?: Query;
  json?: unknown;
  form?: FormData;
  signal?: AbortSignal;
  /** Không phát sự kiện 401 (dùng cho /auth/me khi kiểm tra phiên). */
  silent401?: boolean;
}

export async function api<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const method = (opts.method ?? (opts.json !== undefined || opts.form ? "POST" : "GET")).toUpperCase();
  const headers: Record<string, string> = { Accept: "application/json" };
  let body: BodyInit | undefined;
  if (opts.form) {
    body = opts.form; // trình duyệt tự đặt multipart boundary
  } else if (opts.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.json);
  }
  if (UNSAFE.has(method) && csrfToken) headers["X-CSRF-Token"] = csrfToken;

  const res = await fetch(withQuery(path, opts.query), {
    method,
    headers,
    body,
    credentials: "include",
    signal: opts.signal,
  });
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  let data: unknown = undefined;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = undefined;
    }
  }
  if (!res.ok) {
    if (res.status === 401 && !opts.silent401) unauthorizedListeners.forEach((fn) => fn());
    throw new ApiError(res.status, (data as ErrorEnvelope | undefined)?.error);
  }
  return data as T;
}

/** Thông điệp tiếng Việt cho người dùng theo mã lỗi ổn định của API. */
export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    switch (err.status) {
      case 403:
        return err.code === "CSRF_FAILED" ? "Phiên làm việc không hợp lệ, vui lòng tải lại trang." : err.message;
      case 413:
        return `File quá lớn hoặc quá nhiều trang: ${err.message}`;
      case 415:
        return `Loại file không được hỗ trợ: ${err.message}`;
      case 429:
        return "Thao tác quá nhiều lần, vui lòng thử lại sau ít phút.";
      default:
        return err.message;
    }
  }
  if (err instanceof Error) return err.message;
  return "Đã có lỗi xảy ra";
}
