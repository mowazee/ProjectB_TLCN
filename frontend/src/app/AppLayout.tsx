import { Suspense, useState } from "react";
import { NavLink, Outlet } from "react-router";

import { UserMenu } from "@/features/auth";
import { Loading } from "@/shared/components/ui";
import { SlotList, useSlots } from "@/shared/slots";
import type { NavItem } from "@/shared/types/feature";

import s from "./layout.module.css";

export function AppLayout({ nav }: { nav: NavItem[] }) {
  const { headerItems } = useSlots();
  const [open, setOpen] = useState(false);
  const main = nav.filter((n) => n.group !== "admin");
  const admin = nav.filter((n) => n.group === "admin");
  const link = (n: NavItem) => (
    <NavLink
      key={n.to}
      to={n.to}
      end={n.to === "/"}
      className={({ isActive }) => `${s.link} ${isActive ? s.active : ""}`}
      onClick={() => setOpen(false)}
    >
      {n.label}
    </NavLink>
  );
  return (
    <div className={s.shell}>
      <aside className={`${s.sidebar} ${open ? s.open : ""}`}>
        <div className={s.brand}>Số hóa hồ sơ</div>
        <nav className={s.nav}>
          {main.map(link)}
          {admin.length > 0 && <div className={s.section}>Quản trị</div>}
          {admin.map(link)}
        </nav>
      </aside>
      <div className={s.body}>
        <header className={s.header}>
          <button className={`btn ${s.menuBtn}`} onClick={() => setOpen(!open)} aria-label="Mở menu">
            ☰
          </button>
          <div className="grow" />
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
    <div className="card">
      <h2>Không tìm thấy trang</h2>
      <p className="muted">Trang không tồn tại hoặc tính năng chưa được bật.</p>
    </div>
  );
}
