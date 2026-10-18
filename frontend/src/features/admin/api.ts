import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type Query } from "@/shared/api/client";
import type {
  AuditLog,
  Category,
  CategoryIn,
  CategoryPatch,
  Department,
  Paged,
  Role,
  User,
  UserIn,
  UserPatch,
} from "@/shared/api/types";

export function useUsers(page: number, q: string) {
  return useQuery({
    queryKey: ["users", page, q],
    queryFn: () => api<Paged<User>>("/api/users", { query: { page, page_size: 20, q } }),
    placeholderData: (prev) => prev,
  });
}

export function useRoles() {
  // member_count thay đổi khi gán/gỡ vai trò: useSaveUser làm mới khóa này
  return useQuery({ queryKey: ["roles"], queryFn: () => api<Role[]>("/api/roles"), staleTime: 30_000 });
}

/** FR-12: thành viên của một vai trò (lọc phía server, tối đa 100 người/trang). */
export function useRoleMembers(role: string | null) {
  return useQuery({
    queryKey: ["users", "role", role],
    enabled: role !== null,
    queryFn: () => api<Paged<User>>("/api/users", { query: { role: role ?? undefined, page_size: 100 } }),
  });
}

/** Người dùng đang hoạt động để chọn thêm vào vai trò (tìm theo tên/email). */
export function useUserPicker(q: string) {
  return useQuery({
    queryKey: ["users", "picker", q],
    queryFn: () => api<Paged<User>>("/api/users", { query: { q: q || undefined, is_active: true, page_size: 20 } }),
    placeholderData: (prev) => prev,
  });
}

export function useDepartments() {
  return useQuery({
    queryKey: ["departments"],
    queryFn: () => api<Department[]>("/api/departments"),
    staleTime: 60_000,
  });
}

export function useSaveUser() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id?: string; data: UserIn | UserPatch }) =>
      id ? api<User>(`/api/users/${id}`, { method: "PATCH", json: data }) : api<User>("/api/users", { json: data }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["users"] });
      client.invalidateQueries({ queryKey: ["roles"] });
    },
  });
}

export function useSaveCategory() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id?: number; data: CategoryIn | CategoryPatch }) =>
      id
        ? api<Category>(`/api/categories/${id}`, { method: "PATCH", json: data })
        : api<Category>("/api/categories", { json: data }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["categories"] }),
  });
}

export function useAudit(filters: Query & { page: number }) {
  return useQuery({
    queryKey: ["audit", filters],
    queryFn: () => api<Paged<AuditLog>>("/api/audit", { query: { ...filters, page_size: 25 } }),
    placeholderData: (prev) => prev,
  });
}
