import { api } from "@/shared/api/client";
import type { Session } from "@/shared/api/types";

export function login(username: string, password: string): Promise<Session> {
  return api<Session>("/api/auth/login", { json: { username, password }, silent401: true });
}

export function logout(): Promise<void> {
  return api<void>("/api/auth/logout", { method: "POST" });
}
