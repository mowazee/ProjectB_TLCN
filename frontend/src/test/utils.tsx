import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router";
import { vi } from "vitest";

import type { Session } from "@/shared/api/types";
import { SessionProvider } from "@/shared/session";
import { EMPTY_SLOTS, SlotsProvider, type Slots } from "@/shared/slots";

export interface Call {
  method: string;
  url: string;
  headers: Record<string, string>;
  body: unknown;
}

type Handler = (call: Call) => { status?: number; body?: unknown } | undefined;

/** Giả lập fetch theo "METHOD /đường-dẫn" (khớp tiền tố, bỏ query); ghi lại mọi lời gọi. */
export function mockFetch(handlers: Record<string, Handler | { status?: number; body?: unknown }>) {
  const calls: Call[] = [];
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = (init?.method ?? "GET").toUpperCase();
    const headers = (init?.headers ?? {}) as Record<string, string>;
    let body: unknown = init?.body;
    if (typeof body === "string") body = JSON.parse(body);
    const call = { method, url, headers, body };
    calls.push(call);
    const path = url.split("?")[0];
    const key = Object.keys(handlers)
      .filter((k) => {
        const [m, p] = k.split(" ");
        return m === method && path.startsWith(p);
      })
      .sort((a, b) => b.length - a.length)[0];
    const h = key ? handlers[key] : undefined;
    const res = typeof h === "function" ? h(call) : h;
    const status = res?.status ?? (h ? 200 : 404);
    const payload = res?.body ?? (h ? {} : { error: { code: "HTTP_404", message: "Không tìm thấy" } });
    return new Response(status === 204 ? null : JSON.stringify(payload), { status });
  });
  vi.stubGlobal("fetch", fn);
  return calls;
}

export const SESSION: Session = {
  user: { id: "u1", username: "officer", full_name: "Officer", department_id: 1 },
  roles: ["OFFICER"],
  csrf_token: "csrf-123",
  features: [],
};

export function renderWithProviders(
  ui: ReactElement,
  {
    route = "/",
    slots = EMPTY_SLOTS,
  }: { route?: string | { pathname: string; search?: string; state?: unknown }; slots?: Slots } = {},
) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <SessionProvider>
        <SlotsProvider value={slots}>
          <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
        </SlotsProvider>
      </SessionProvider>
    </QueryClientProvider>,
  );
}
