import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/shared/api/client";
import type { Account, AccountPatch, PasswordIn } from "@/shared/api/types";
import { SESSION_KEY } from "@/shared/session";

export function useAccount() {
  return useQuery({ queryKey: ["account"], queryFn: () => api<Account>("/api/account") });
}

export function useUpdateAccount() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (data: AccountPatch) => api<Account>("/api/account", { method: "PATCH", json: data }),
    onSuccess: (account) => {
      client.setQueryData(["account"], account);
      client.invalidateQueries({ queryKey: SESSION_KEY }); // họ tên trên thanh tiêu đề
    },
  });
}

/** FR-09: server xoay phiên (Set-Cookie mới, thu hồi các phiên khác) -> lấy lại session để có csrf_token mới. */
export function useChangePassword() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (data: PasswordIn) => api<void>("/api/account/password", { json: data }),
    onSuccess: () => client.refetchQueries({ queryKey: SESSION_KEY }),
  });
}
