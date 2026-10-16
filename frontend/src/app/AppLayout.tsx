import { Circle, FileQuestion, Menu, ScanText, Search } from "lucide-react";
import { Suspense, useState, type FormEvent } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router";

import { UserMenu } from "@/features/auth";
import { ThemeToggle } from "@/shared/components/ThemeToggle";
import { Loading } from "@/shared/components/ui";
import { SlotList, useSlots } from "@/shared/slots";
import type { NavItem } from "@/shared/types/feature";

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

export function AppLayout({ nav }: { nav: NavItem[] }) {
  const { headerItems } = useSlots();
  const [open, setOpen] = useState(false);
  const main = nav.filter((n) => n.group !== "admin");
  const admin = nav.filter((n) => n.group === "admin");
  const link = (n: NavItem) => {
    const Icon = n.icon ?? Circle;
    return (
      <NavLink
        key={n.to}
        to={n.to}
        end={n.to === "/"}
        className={({ isActive }) => `${s.link} ${isActive ? s.active : ""}`}
        onClick={() => setOpen(false)}
      >
        <Icon size={18} aria-hidden />
        <span>{n.label}</span>
      </NavLink>
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
          <div className={s.section}>Chức năng</div>
          {main.map(link)}
          {admin.length > 0 && <div className={s.section}>Quản trị</div>}
          {admin.map(link)}
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
