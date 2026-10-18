import { Circle, FileQuestion, Menu, ScanText, Search } from "lucide-react";
import { Suspense, useState, type FormEvent } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router";

import { UserMenu } from "@/features/auth";
import { ThemeToggle } from "@/shared/components/ThemeToggle";
import { Loading } from "@/shared/components/ui";
import { SlotList, useSlots } from "@/shared/slots";
import type { NavGroup, NavItem } from "@/shared/types/feature";

import { activeNavTo } from "./registry";
import s from "./layout.module.css";

/** Ô tìm nhanh trên thanh tiêu đề: chuyển sang /search?q=… (FR-06). */
function QuickSearch() {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const term = q.trim();
    if (!term) return;
    navigate(`/search?q=${encodeURIComponent(term)}`);
    setQ("");
  };
  return (
    <form className={s.search} onSubmit={submit} role="search">
      <Search size={16} className={s.searchIcon} aria-hidden />
      <input
        className={s.searchInput}
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Tìm trong nội dung tài liệu…"
        aria-label="Tìm nhanh trong nội dung tài liệu"
      />
    </form>
  );
}

/** Thứ tự và tiêu đề nhóm menu (v0.7); nhóm không có mục nào được người dùng thấy thì ẩn cả tiêu đề. */
const NAV_GROUPS: { id: NavGroup; label: string | null }[] = [
  { id: "main", label: null },
  { id: "documents", label: "Tài liệu" },
  { id: "workflow", label: "Quy trình" },
  { id: "admin", label: "Quản trị" },
  { id: "personal", label: "Cá nhân" },
];

export function AppLayout({ nav }: { nav: NavItem[] }) {
  const { headerItems } = useSlots();
  const [open, setOpen] = useState(false);
  const active = activeNavTo(nav, useLocation().pathname);
  const link = (n: NavItem) => {
    const Icon = n.icon ?? Circle;
    return (
      // Link thay NavLink: NavLink tự gắn aria-current khi khớp tiền tố, sáng cả "Tài liệu" lẫn "Thùng rác"
      <Link
        key={n.to}
        to={n.to}
        aria-current={n.to === active ? "page" : undefined}
        className={`${s.link} ${n.to === active ? s.active : ""}`}
        onClick={() => setOpen(false)}
      >
        <Icon size={18} aria-hidden />
        <span>{n.label}</span>
      </Link>
    );
  };
  return (
    <div className={s.shell}>
      <aside className={`${s.sidebar} ${open ? s.open : ""}`}>
        <Link to="/" className={s.brand} onClick={() => setOpen(false)}>
          <span className={s.logo}>
            <ScanText size={20} aria-hidden />
          </span>
          <span>
            <strong>Số hóa hồ sơ</strong>
            <small>Quản lý tài liệu số</small>
          </span>
        </Link>
        <nav className={s.nav}>
          {NAV_GROUPS.map((g) => {
            const items = nav.filter((n) => (n.group ?? "main") === g.id);
            if (!items.length) return null;
            return (
              <div key={g.id} role="group" aria-label={g.label ?? "Tổng quan"}>
                {g.label && <div className={s.section}>{g.label}</div>}
                {items.map(link)}
              </div>
            );
          })}
        </nav>
        <div className={s.sideFoot}>Tiểu luận chuyên ngành · Nhóm 3</div>
      </aside>
      {open && <div className={s.scrim} onClick={() => setOpen(false)} aria-hidden />}
      <div className={s.body}>
        <header className={s.header}>
          <button className={`btn btn-icon ${s.menuBtn}`} onClick={() => setOpen(!open)} aria-label="Mở menu">
            <Menu size={20} aria-hidden />
          </button>
          <QuickSearch />
          <div className="grow" />
          <ThemeToggle />
          <SlotList items={headerItems} props={{}} />
          <UserMenu />
        </header>
        <main className={s.main}>
          <Suspense fallback={<Loading />}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  );
}

export function NotFound() {
  return (
    <div className={`card ${s.notFound}`}>
      <FileQuestion size={40} aria-hidden />
      <h2>Không tìm thấy trang</h2>
      <p className="muted">Trang không tồn tại hoặc tính năng chưa được bật.</p>
      <Link to="/" className="btn">
        Về trang tổng quan
      </Link>
    </div>
  );
}
