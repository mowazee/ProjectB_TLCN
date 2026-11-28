import { FileSearch, History, ScanText, ShieldCheck, Workflow } from "lucide-react";
import type { ReactNode } from "react";

import { ThemeToggle } from "@/shared/components/ThemeToggle";

import s from "./auth.module.css";

/** Khung chung của các trang chưa đăng nhập: giới thiệu hệ thống | nội dung (đăng nhập, quên/đặt lại mật khẩu). */
export function AuthShell({ children }: { children: ReactNode }) {
  return (
    <div className={s.wrap}>
      <section className={s.hero} aria-label="Giới thiệu hệ thống">
        <div className={s.heroBrand}>
          <span className={s.heroLogo}>
            <ScanText size={24} aria-hidden />
          </span>
          Số hóa hồ sơ
        </div>
        <div>
          <h2 className={s.heroTitle}>Hệ thống số hóa hồ sơ tài liệu doanh nghiệp</h2>
          <p className={s.heroLead}>Từ bản giấy đến dữ liệu tra cứu được trong vài phút.</p>
          <ul className={s.features}>
            {FEATURES.map(({ icon: Icon, title, text }) => (
              <li key={title}>
                <span>
                  <Icon size={18} aria-hidden />
                </span>
                <div>
                  <strong>{title}</strong>
                  {text}
                </div>
              </li>
            ))}
          </ul>
        </div>
        <small className={s.heroFoot}>Tiểu luận chuyên ngành · UTE · Nhóm 3</small>
      </section>
      <div className={s.side}>
        <ThemeToggle className={s.themeToggle} />
        {children}
      </div>
    </div>
  );
}

const FEATURES = [
  { icon: ScanText, title: "OCR tự động", text: "Nhận dạng chữ in và chữ viết tay tiếng Việt ngay sau khi tải lên." },
  { icon: FileSearch, title: "Tìm kiếm toàn văn", text: "Tìm theo nội dung, mở đúng trang và vị trí từ khóa." },
  { icon: Workflow, title: "Duyệt và mượn hồ sơ", text: "Quy trình gửi duyệt, xuất bản, mượn và trả bản cứng." },
  { icon: History, title: "Lưu vết đầy đủ", text: "Nhật ký mọi thao tác, so sánh phiên bản, khôi phục thay đổi." },
  {
    icon: ShieldCheck,
    title: "Phân quyền chặt chẽ",
    text: "Chỉ xem tài liệu của mình và phòng ban, kiểm tra tại máy chủ.",
  },
];
