import { describe, expect, it, vi } from "vitest";

import { mockFetch } from "@/test/utils";

import { api, ApiError, onUnauthorized, setCsrfToken, withQuery } from "./client";

describe("api client (SDD mục 13-14)", () => {
  it("gửi cookie, X-CSRF-Token chỉ cho thao tác ghi", async () => {
    const calls = mockFetch({ "GET /api/x": { body: { ok: 1 } }, "POST /api/x": { body: { ok: 2 } } });
    setCsrfToken("tok");
    await api("/api/x");
    await api("/api/x", { json: { a: 1 } });
    expect(calls[0].headers["X-CSRF-Token"]).toBeUndefined();
    expect(calls[1].headers["X-CSRF-Token"]).toBe("tok");
    expect(calls[1].headers["Content-Type"]).toBe("application/json");
    const init = vi.mocked(fetch).mock.calls[0][1] as RequestInit;
    expect(init.credentials).toBe("include");
  });

  it("FormData không tự đặt Content-Type", async () => {
    const calls = mockFetch({ "POST /api/documents": { status: 201, body: {} } });
    const form = new FormData();
    form.append("category_id", "1");
    await api("/api/documents", { form });
    expect(calls[0].headers["Content-Type"]).toBeUndefined();
  });

  it("chuẩn lỗi -> ApiError có code, fields, request_id", async () => {
    mockFetch({
      "POST /api/users": {
        status: 422,
        body: {
          error: {
            code: "VALIDATION_ERROR",
            message: "Dữ liệu không hợp lệ",
            fields: { email: "x" },
            request_id: "r1",
          },
        },
      },
    });
    const err = await api("/api/users", { json: {} }).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 422, code: "VALIDATION_ERROR", fields: { email: "x" }, requestId: "r1" });
  });

  it("401 phát sự kiện để chuyển về đăng nhập (trừ khi silent401)", async () => {
    mockFetch({ "GET /api/documents": { status: 401, body: { error: { code: "UNAUTHENTICATED", message: "x" } } } });
    const listener = vi.fn();
    const off = onUnauthorized(listener);
    await api("/api/documents").catch(() => undefined);
    await api("/api/documents", { silent401: true }).catch(() => undefined);
    off();
    expect(listener).toHaveBeenCalledTimes(1);
  });

  it("withQuery bỏ giá trị rỗng", () => {
    expect(withQuery("/a", { q: "x y", page: 1, empty: "", none: undefined })).toBe("/a?q=x+y&page=1");
  });
});
