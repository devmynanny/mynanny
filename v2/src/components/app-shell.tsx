"use client";

import { Brand } from "@/components/brand";
import { PoweredByTiqet } from "@/components/powered-by-tiqet";
import { NotificationBell } from "@/components/notification-bell";
import {
  CalendarDays,
  ClipboardList,
  Database,
  Heart,
  Home,
  Landmark,
  LogOut,
  Menu,
  MessageCircle,
  Search,
  Settings,
  ShieldCheck,
  ShieldAlert,
  Undo2,
  UserRound,
  Video,
  WalletCards,
  Award,
  BriefcaseBusiness,
  UsersRound,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { apiFetch, apiJson } from "@/lib/api";

type Role = "parent" | "nanny" | "admin";
const roleLinks = {
  parent: [
    ["/dashboard", "Home", Home],
    ["/caregivers", "Find a nanny", Search],
    ["/bookings", "Bookings", CalendarDays],
    ["/placements", "Permanent placements", BriefcaseBusiness],
    ["/favorites", "Favourites", Heart],
    ["/profile", "Profile", UserRound],
  ],
  nanny: [
    ["/dashboard", "Home", Home],
    ["/interview", "Video interview", Video],
    ["/availability", "Availability", CalendarDays],
    ["/requests", "Requests", Heart],
    ["/placements", "Permanent placements", BriefcaseBusiness],
    ["/payout-details", "Payout details", Landmark],
    ["/profile", "Profile", UserRound],
  ],
  admin: [
    ["/dashboard", "Overview", Home],
    ["/review", "Candidate review", ShieldCheck],
    ["/users", "Users & records", Database],
    ["/bookings", "Bookings", CalendarDays],
    ["/placements", "Permanent placements", BriefcaseBusiness],
    ["/finance", "Finance", WalletCards],
    ["/refunds", "Refunds", Undo2],
    ["/operations", "Safety centre", ShieldAlert],
    ["/communicator", "Communicator", MessageCircle],
    ["/audit", "Audit logs", ClipboardList],
    ["/trust", "Trust configuration", Award],
    ["/team", "Team access", UsersRound],
    ["/profile", "Settings", Settings],
  ],
} as const;

export function AppShell({
  role,
  name,
  children,
}: {
  role: Role;
  name: string;
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [accessLevel, setAccessLevel] = useState<string | null>(null);
  useEffect(() => {
    if (role === "admin") apiJson<{ access_level: string }>("/admin/access/me").then((data) => setAccessLevel(data.access_level)).catch(() => setAccessLevel("superadmin"));
  }, [role]);
  const links = roleLinks[role].filter(([href]) => {
    if (role !== "admin" || !accessLevel || accessLevel === "superadmin") return true;
    if (accessLevel === "finance") return ["/dashboard", "/finance", "/refunds", "/communicator"].includes(href);
    return !["/finance", "/refunds", "/audit", "/trust", "/team", "/profile"].includes(href);
  });
  async function logout() {
    await apiFetch("/auth/logout", { method: "POST" }).catch(() => undefined);
    router.push("/login");
  }
  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[290px_1fr]">
      <header className="sticky top-0 z-30 flex h-[74px] items-center justify-between border-b border-[var(--line)] bg-white/95 px-5 backdrop-blur lg:hidden">
        <Brand compact />
        <div className="flex items-center gap-1"><NotificationBell/><button className="btn-quiet !min-h-10 !px-3" onClick={() => setOpen(!open)} aria-label="Open navigation">{open ? <X /> : <Menu />}</button></div>
      </header>
      <aside
        className={`${open ? "flex" : "hidden"} fixed inset-x-0 top-[74px] bottom-0 z-20 flex-col overflow-y-auto border-r border-[var(--line)] bg-white p-5 lg:sticky lg:top-0 lg:flex lg:h-screen`}
      >
        <div className="mb-8 hidden lg:block">
          <Brand sidebar />
        </div>
        <div className="mb-5 flex items-start justify-between gap-2 rounded-2xl bg-[var(--blue-pale)] p-4">
          <div><div className="text-sm font-bold">{name || "Welcome"}</div><div className="mt-1 text-xs capitalize text-[var(--muted)]">{role === "admin" ? "My Nanny team" : `${role} account`}</div></div>
          <div className="hidden lg:block"><NotificationBell/></div>
        </div>
        <nav className="grid gap-1" aria-label="Main navigation">
          {links.map(([href, label, Icon]) => {
            const active = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                onClick={() => setOpen(false)}
                className={`flex min-h-11 items-center gap-3 rounded-xl px-3 text-sm font-bold transition ${active ? "bg-[var(--blue-dark)] text-white" : "text-[var(--muted)] hover:bg-[var(--blue-pale)] hover:text-[var(--ink)]"}`}
              >
                <Icon size={18} />
                {label}
              </Link>
            );
          })}
        </nav>
        <button
          onClick={logout}
          className="mt-auto flex min-h-11 items-center gap-3 rounded-xl px-3 text-sm font-bold text-[var(--muted)] hover:bg-red-50 hover:text-red-700"
        >
          <LogOut size={18} />
          Log out
        </button>
        <div className="mt-4 border-t border-[var(--line)] pt-4">
          <PoweredByTiqet className="max-w-full" />
        </div>
      </aside>
      <main className="min-w-0 px-4 py-6 sm:px-8 lg:px-10 lg:py-9">
        {children}
      </main>
    </div>
  );
}
