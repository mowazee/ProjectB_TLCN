import { ArrowLeft } from "lucide-react";
import { Link, useLocation } from "react-router";

import { useSession } from "@/shared/session";

import { readListSearch, type BackState } from "./backLink";

export function BackToList() {
  const { session } = useSession();
  const state = useLocation().state as BackState | null;
  // chỉ nhận đường dẫn nội bộ ("/..." nhưng không "//host")
  const from = state?.from?.startsWith("/") && !state.from.startsWith("//") ? state.from : null;
  const to = from ?? `/documents${readListSearch(session?.user.id)}`;
  return (
    <Link className="btn btn-ghost btn-sm" to={to} style={{ alignSelf: "flex-start" }}>
      <ArrowLeft size={16} aria-hidden /> Quay lại {(from && state?.fromLabel) || "danh sách tài liệu"}
    </Link>
  );
}
