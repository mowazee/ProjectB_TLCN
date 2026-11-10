import { BookOpen } from "lucide-react";

import { EmptyState, PageHeader } from "@/shared/components/ui";

/** Trang Hướng dẫn sử dụng (v0.14): để trống, sau này đặt các tài liệu hướng dẫn sử dụng hệ thống tại đây. */
export function GuidePage() {
  return (
    <div className="stack">
      <PageHeader icon={BookOpen} title="Hướng dẫn sử dụng" subtitle="Tài liệu hướng dẫn sử dụng hệ thống." />
      <div className="card">
        <EmptyState icon={BookOpen}>Chưa có tài liệu hướng dẫn. Nội dung sẽ được cập nhật sau.</EmptyState>
      </div>
    </div>
  );
}
