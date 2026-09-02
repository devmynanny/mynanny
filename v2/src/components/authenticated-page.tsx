"use client";
import { AppShell } from "@/components/app-shell";
import { apiJson } from "@/lib/api";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
type Me = { name: string; role: string; is_admin?: boolean };
export function AuthenticatedPage({ children, returnTo }: { children: (role: "parent"|"nanny"|"admin") => React.ReactNode; returnTo?: string }) {
  const router = useRouter();
  const [me,setMe]=useState<Me|null>(null); const [failed,setFailed]=useState(false);
  useEffect(()=>{apiJson<Me>("/auth/me").then(setMe).catch(()=>setFailed(true));},[]);
  useEffect(()=>{if(failed) router.replace(returnTo ? `/login?next=${encodeURIComponent(returnTo)}` : "/login");},[failed,returnTo,router]);
  if(failed)return null; if(!me)return <main className="flex min-h-screen items-center justify-center text-[var(--muted)]">Loading...</main>;
  const role = me.is_admin ? "admin" : me.role === "nanny" ? "nanny" : "parent";
  return <AppShell role={role} name={me.name}>{children(role)}</AppShell>;
}
