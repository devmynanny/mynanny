"use client";

import { Brand } from "@/components/brand";
import { apiJson } from "@/lib/api";
import { ArrowRight, ShieldCheck } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useEffect, useState } from "react";

type Invite = { email: string; status: string; access_level: string; expires_at: string };

export default function AdminInvitePage() { return <Suspense fallback={<div className="p-10">Loading invitation...</div>}><InviteForm/></Suspense>; }
function InviteForm() {
  const token = useSearchParams().get("token") || ""; const router = useRouter(); const [invite, setInvite] = useState<Invite | null>(null); const [name, setName] = useState(""); const [password, setPassword] = useState(""); const [message, setMessage] = useState("");
  useEffect(() => { if (!token) return; apiJson<Invite>(`/auth/admin-invite/${token}`).then(setInvite).catch((error) => setMessage(error instanceof Error ? error.message : "Unable to open invitation.")); }, [token]);
  async function accept(event: FormEvent) { event.preventDefault(); setMessage(""); try { await apiJson("/auth/admin-invite/accept", { method: "POST", body: JSON.stringify({ token, name, password }) }); router.push("/dashboard"); } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to accept invitation."); } }
  return <main className="min-h-screen bg-[var(--canvas)] p-5 sm:p-10"><div className="mx-auto max-w-2xl"><Brand/><section className="card mt-10 overflow-hidden"><div className="bg-[var(--blue-dark)] p-8 text-white"><ShieldCheck size={36}/><div className="eyebrow mt-5 !text-sky-200">My Nanny team invitation</div><h1 className="display mt-2 text-4xl">Join the operations team.</h1></div><form className="grid gap-5 p-8" onSubmit={accept}>{invite && <div className="rounded-2xl bg-[var(--blue-pale)] p-4"><div className="font-bold">{invite.email}</div><div className="mt-1 text-sm capitalize text-[var(--muted)]">{invite.access_level} access</div></div>}<label className="text-sm font-bold">Full name<input className="field mt-2" value={name} onChange={(e) => setName(e.target.value)} required/></label><label className="text-sm font-bold">Create password<input className="field mt-2" type="password" minLength={6} value={password} onChange={(e) => setPassword(e.target.value)} required/></label>{(!token || message) && <div className="rounded-xl bg-amber-50 p-4 text-amber-900">{message || "This invitation link is incomplete."}</div>}<button className="btn-primary" disabled={!invite || invite.status !== "pending"}>Accept invitation <ArrowRight size={18}/></button></form></section></div></main>;
}
