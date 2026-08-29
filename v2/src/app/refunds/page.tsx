"use client";

import { AuthenticatedPage } from "@/components/authenticated-page";
import { apiJson } from "@/lib/api";
import { Check, LoaderCircle, RefreshCw, Undo2, X } from "lucide-react";
import { useEffect, useEffectEvent, useState } from "react";

type Refund = { job_id: number; request_id: number; status: string; refund_status?: string | null; refund_cents?: number | null; parent_user_id: number; nanny_id?: number | null; created_at?: string | null };
const money = (value?: number | null) => `R${(Number(value || 0) / 100).toLocaleString("en-ZA", { minimumFractionDigits: 2 })}`;

export default function RefundsPage() { return <AuthenticatedPage>{(role) => role === "admin" ? <Refunds /> : <div className="card mx-auto max-w-xl p-8 text-center"><h1 className="text-2xl font-bold">Team access only</h1></div>}</AuthenticatedPage>; }

function Refunds() {
  const [filter, setFilter] = useState("pending_review"); const [rows, setRows] = useState<Refund[]>([]);
  const [loading, setLoading] = useState(true); const [busy, setBusy] = useState<number | null>(null); const [message, setMessage] = useState("");
  async function load() { setLoading(true); setMessage(""); try { const data = await apiJson<{ results: Refund[] }>(`/admin/refunds?status=${filter}`); setRows(data.results || []); } catch (e) { setMessage(e instanceof Error ? e.message : "Unable to load refunds."); } finally { setLoading(false); } }
  const loadForFilter = useEffectEvent(load);
  useEffect(() => { Promise.resolve().then(() => loadForFilter()); }, [filter]);
  async function decide(row: Refund, decision: "approve" | "deny") {
    const promptText = decision === "approve" ? `Approve the ${money(row.refund_cents)} refund for booking #${row.job_id}? Add an optional internal reason:` : `Why is the refund for booking #${row.job_id} being declined?`;
    const reason = window.prompt(promptText, "") ?? null; if (reason === null || (decision === "deny" && !reason.trim())) return;
    setBusy(row.job_id); setMessage("");
    try { await apiJson(`/admin/booking-requests/${row.job_id}/refund/${decision}`, { method: "POST", body: JSON.stringify({ reason: reason.trim() || null }) }); setMessage(`Refund ${decision === "approve" ? "approved" : "declined"}.`); await load(); }
    catch (e) { setMessage(e instanceof Error ? e.message : "Unable to update this refund."); } finally { setBusy(null); }
  }
  return <div className="mx-auto max-w-6xl"><div className="eyebrow">Payment operations</div><div className="mt-2 flex flex-wrap items-end justify-between gap-4"><div><h1 className="display text-4xl sm:text-5xl">Refund review.</h1><p className="mt-3 text-[var(--muted)]">Review cancellation outcomes before money is returned through Paystack.</p></div><button className="btn-secondary" onClick={() => void load()}><RefreshCw size={17}/>Refresh</button></div>
    <div className="card mt-7 flex flex-wrap items-center justify-between gap-4 p-4"><div className="flex items-center gap-3"><span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[var(--blue-pale)] text-[var(--blue-dark)]"><Undo2/></span><b>{rows.length} records</b></div><select className="field max-w-56" value={filter} onChange={(e) => setFilter(e.target.value)}><option value="pending_review">Awaiting review</option><option value="processed">Processed</option><option value="denied">Declined</option><option value="failed">Failed</option><option value="all">All paid bookings</option></select></div>
    {message && <div className="mt-5 rounded-2xl bg-[var(--blue-pale)] p-4 font-semibold">{message}</div>}
    <section className="card mt-6 overflow-hidden">{loading ? <div className="flex min-h-64 items-center justify-center"><LoaderCircle className="animate-spin"/></div> : rows.length ? <div className="divide-y divide-[var(--line)]">{rows.map((row) => <article className="grid gap-5 p-6 sm:grid-cols-[1fr_auto]" key={row.request_id}><div><div className="flex flex-wrap items-center gap-2"><h2 className="text-xl font-bold">Booking #{row.job_id}</h2><span className="pill capitalize">{(row.refund_status || "Not requested").replaceAll("_", " ")}</span></div><div className="mt-3 grid gap-2 text-sm sm:grid-cols-3"><span>Refund <b>{money(row.refund_cents)}</b></span><span>Parent <b>#{row.parent_user_id}</b></span><span>Request <b>#{row.request_id}</b></span></div><p className="mt-3 text-xs text-[var(--muted)]">Requested {row.created_at ? new Date(row.created_at).toLocaleString("en-ZA") : "date unavailable"}</p></div>{row.refund_status === "pending_review" && <div className="flex flex-wrap items-center gap-2"><button className="btn-primary" disabled={busy === row.job_id} onClick={() => void decide(row, "approve")}><Check size={17}/>Approve refund</button><button className="btn-secondary text-red-700" disabled={busy === row.job_id} onClick={() => void decide(row, "deny")}><X size={17}/>Decline</button></div>}</article>)}</div> : <div className="p-12 text-center"><Check className="mx-auto text-emerald-600" size={34}/><h2 className="mt-4 text-xl font-bold">No refunds in this queue</h2><p className="mt-2 text-[var(--muted)]">There is nothing requiring action for this filter.</p></div>}</section></div>;
}
