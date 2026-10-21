import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/shared/api/client";
import type { Job } from "@/shared/api/types";

export const POLL_MS = Number(import.meta.env.VITE_JOB_POLL_MS ?? 2000);
const DONE = new Set(["completed", "failed"]);

/** Poll GET /api/jobs/{id} mỗi ~2 giây; dừng khi completed/failed, unmount, mất quyền hoặc logout. */
export function useJob(jobId: string | null | undefined, onDone?: (job: Job) => void) {
  return useQuery({
    queryKey: ["job", jobId],
    enabled: Boolean(jobId),
    queryFn: async () => {
      const job = await api<Job>(`/api/jobs/${jobId}`);
      if (DONE.has(job.status)) onDone?.(job);
      return job;
    },
    refetchInterval: (q) => {
      const data = q.state.data;
      if (q.state.error) return false;
      return data && DONE.has(data.status) ? false : POLL_MS;
    },
    retry: 1,
  });
}

/** FR-04 (v0.10): dừng job đang chờ/đang xử lý (job đang chạy dừng sau trang hiện tại). */
export function useCancelJob() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) => api<Job>(`/api/jobs/${jobId}/cancel`, { method: "POST" }),
    onSuccess: (job) => {
      client.setQueryData(["job", job.id], job);
      client.invalidateQueries({ queryKey: ["documents"] });
      client.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
}

export function useRetryJob() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) => api<Job>(`/api/jobs/${jobId}/retry`, { method: "POST" }),
    onSuccess: (job) => {
      client.setQueryData(["job", job.id], job);
      client.invalidateQueries({ queryKey: ["documents"] });
    },
  });
}
