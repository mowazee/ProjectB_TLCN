import { useEffect } from "react";

import { useSession } from "@/shared/session";

/**
 * FR-07 (v0.7): nút quay lại danh sách giữ bộ lọc. Danh sách ghi query string vào sessionStorage (theo người dùng),
 * nên đi qua trang xem/sửa OCR rồi mới về chi tiết vẫn quay lại đúng bộ lọc. Trang khác mở chi tiết (hàng đợi,
 * duyệt...) truyền state { from, fromLabel } để quay lại chính trang đó.
 */
export interface BackState {
  from?: string;
  fromLabel?: string;
}

const key = (userId: string | undefined) => `documents.listSearch:${userId ?? ""}`;

export function readListSearch(userId: string | undefined): string {
  try {
    return sessionStorage.getItem(key(userId)) ?? "";
  } catch {
    return "";
  }
}

/** Gọi trong trang danh sách: ghi nhớ bộ lọc hiện tại. */
export function useRememberListSearch(search: string) {
  const { session } = useSession();
  const userId = session?.user.id;
  useEffect(() => {
    try {
      sessionStorage.setItem(key(userId), search);
    } catch {
      // trình duyệt chặn storage: nút quay lại về danh sách không bộ lọc
    }
  }, [userId, search]);
}
