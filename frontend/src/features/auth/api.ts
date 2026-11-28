import { api } from "@/shared/api/client";
import type { Session } from "@/shared/api/types";

export function login(username: string, password: string): Promise<Session> {
  return api<Session>("/api/auth/login", { json: { username, password }, silent401: true });
}

export function logout(): Promise<void> {
  return api<void>("/api/auth/logout", { method: "POST" });
}

// ---------------------------------------------------------------- v0.17 quên mật khẩu
export interface AuthOptions {
  password_reset: boolean;
  password_reset_ttl_minutes: number;
}

export function getAuthOptions(): Promise<AuthOptions> {
  return api<AuthOptions>("/api/auth/options", { silent401: true });
}

export function forgotPassword(login: string): Promise<{ message: string }> {
  return api<{ message: string }>("/api/auth/forgot-password", { json: { login }, silent401: true });
}

export function checkResetLink(token: string): Promise<{ username: string }> {
  return api<{ username: string }>(`/api/auth/reset-password/${encodeURIComponent(token)}`, { silent401: true });
}

export function resetPassword(token: string, newPassword: string): Promise<{ message: string; reactivated: boolean }> {
  return api<{ message: string; reactivated: boolean }>(`/api/auth/reset-password/${encodeURIComponent(token)}`, {
    json: { new_password: newPassword },
    silent401: true,
  });
}
