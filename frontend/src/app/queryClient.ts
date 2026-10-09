import { QueryClient } from "@tanstack/react-query";

import { ApiError } from "@/shared/api/client";

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // GET retry hữu hạn, không retry lỗi 4xx (SDD mục 13); mutation không tự retry
        retry: (count, err) => !(err instanceof ApiError && err.status < 500) && count < 2,
        refetchOnWindowFocus: false,
      },
      mutations: { retry: false },
    },
  });
}
