"use client";

import { AuthenticatedPage } from "@/components/authenticated-page";
import { apiJson } from "@/lib/api";
import { AlertTriangle, CheckCircle2, LoaderCircle, RefreshCw } from "lucide-react";
import { useEffect, useEffectEvent, useState } from "react";

type Summary = Record<string, number | string>;
type Payout = {
  kind: string; booking_id: number; booking_request_id?: number | null;
  parent_name?: string | null; nanny_name?: string | null; gross_amount_cents: number;
  debt_deducted_cents: number; net_amount_cents: number; hold_until?: string | null;
  released_at?: string | null; state: string; bank_name?: string | null;
  recipient_code?: string | null; transfer_ready: boolean;
};
type Reconciliation = {
  booking_request_id: number; status: string; paid_at?: string | null;
  total_paid_cents: number; booking_fee_cents: number; wage_cents: number;
  refund_cents: number; payout_released_cents: number; debt_deducted_cents: number;
  problems: string[];
};

const money = (value: number | string | undefined) => `R${(Number(value || 0) / 100).toLocaleString("en-ZA", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const dateTime = (value?: string | null) => value ? new Date(value).toLocaleString("en-ZA") : "Not yet";
const label = (value: string) => value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());

export default function FinancePage() {
  return <AuthenticatedPage>{(role) => role === "admin" ? <Finance /> : <AccessDenied />}</AuthenticatedPage>;
}

function Finance() {
  const [range, setRange] = useState("month");
  const [status, setStatus] = useState("all");
  const [summary, setSummary] = useState<Summary | null>(null);
  const [payouts, setPayouts] = useState<Payout[]>([]);
  const [reconciliation, setReconciliation] = useState<Reconciliation[]>([]);
  const [mismatchCount, setMismatchCount] = useState(0);
  const [onlyMismatches, setOnlyMismatches] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true); setError("");
    try {
      const query = `range=${range}`;
      const [summaryResult, payoutResult, reconciliationResult] = await Promise.all([
        apiJson<Summary>(`/admin/accounting/summary?${query}`),
        apiJson<{ results: Payout[] }>(`/admin/accounting/payouts?${query}&status=${status}`),
        apiJson<{ results: Reconciliation[]; mismatch_count: number }>(`/admin/accounting/reconciliation?${query}&only_mismatches=${onlyMismatches}`),
      ]);
      setSummary(summaryResult); setPayouts(payoutResult.results || []);
      setReconciliation(reconciliationResult.results || []); setMismatchCount(reconciliationResult.mismatch_count || 0);
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to load financial operations."); }
    finally { setLoading(false); }
  }
  const loadForFilters = useEffectEvent(load);
  useEffect(() => { Promise.resolve().then(() => loadForFilters()); }, [range, status, onlyMismatches]);

  const metrics = summary ? [
    ["Payments processed", money(summary.payments_processed_cents), `${summary.payments_processed_count || 0} transactions`],
    ["Company income", money(summary.company_income_cents), `Net ${money(summary.net_company_income_cents)}`],
    ["Nanny wages", money(summary.nanny_income_cents), `${summary.total_paid_jobs || 0} paid jobs`],
    ["Refunded", money(summary.refunds_processed_cents), `${summary.refunds_processed_count || 0} processed`],
    ["Payouts released", money(summary.payouts_released_cents), `${summary.payouts_released_count || 0} releases`],
    ["Payouts pending", money(summary.payouts_pending_cents), `Overtime ${money(summary.overtime_pending_cents)}`],
    ["Debt deducted", money(summary.debt_deducted_cents), `${summary.debt_deducted_count || 0} deductions`],
    ["Debt outstanding", money(summary.debt_outstanding_cents), "Current total balance"],
  ] : [];

  return <div className="mx-auto max-w-[1500px]">
    <div className="eyebrow">Financial operations</div>
    <div className="mt-2 flex flex-wrap items-end justify-between gap-4"><div><h1 className="display text-4xl sm:text-5xl">Finance & payouts.</h1><p className="mt-3 text-[var(--muted)]">Monitor money collected, nanny earnings, payout readiness and ledger integrity.</p></div><button className="btn-secondary" onClick={() => void load()} disabled={loading}><RefreshCw size={17} className={loading ? "animate-spin" : ""}/>Refresh</button></div>
    <div className="card mt-7 flex flex-wrap gap-4 p-4"><label className="min-w-52"><span className="mb-2 block text-xs font-bold uppercase text-[var(--muted)]">Reporting period</span><select className="field" value={range} onChange={(e) => setRange(e.target.value)}><option value="day">Today</option><option value="week">Last 7 days</option><option value="month">Last 30 days</option><option value="quarter">Last 3 months</option><option value="year">Last 12 months</option></select></label></div>
    {error && <div role="alert" className="mt-5 rounded-2xl bg-red-50 p-4 text-red-800">{error}</div>}
    {loading && !summary ? <Loading /> : <>
      <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{metrics.map(([title, value, note]) => <div className="card p-5" key={title}><div className="text-xs font-bold uppercase tracking-wider text-[var(--muted)]">{title}</div><div className="mt-3 text-3xl font-extrabold">{value}</div><div className="mt-2 text-sm text-[var(--muted)]">{note}</div></div>)}</div>
      <section className="card mt-6 overflow-hidden"><header className="flex flex-wrap items-end justify-between gap-4 border-b border-[var(--line)] p-6"><div><div className="eyebrow">Nanny earnings</div><h2 className="mt-2 text-2xl font-bold">Payout reconciliation</h2></div><select className="field max-w-52" value={status} onChange={(e) => setStatus(e.target.value)}><option value="all">All payouts</option><option value="pending">Pending</option><option value="released">Released</option><option value="blocked">Blocked</option></select></header><div className="divide-y divide-[var(--line)]">{payouts.length ? payouts.map((item) => <div className="grid gap-4 p-6 lg:grid-cols-[1fr_auto]" key={`${item.kind}-${item.booking_id}`}><div><div className="flex flex-wrap items-center gap-2"><b>{item.kind === "overtime" ? "Overtime" : "Base payout"} · Booking #{item.booking_id}</b><span className="pill">{label(item.state)}</span></div><p className="mt-2 text-sm text-[var(--muted)]">{item.parent_name || "Unknown parent"} → {item.nanny_name || "Unknown nanny"}</p><div className="mt-3 grid gap-2 text-sm sm:grid-cols-3"><span>Gross <b>{money(item.gross_amount_cents)}</b></span><span>Debt <b>{money(item.debt_deducted_cents)}</b></span><span>Net <b>{money(item.net_amount_cents)}</b></span></div><p className="mt-3 text-xs text-[var(--muted)]">Hold: {dateTime(item.hold_until)} · Released: {dateTime(item.released_at)} · {item.bank_name || "Bank missing"}</p></div><div className={`flex items-center gap-2 font-bold ${item.transfer_ready ? "text-emerald-700" : "text-amber-700"}`}>{item.transfer_ready ? <CheckCircle2 size={18}/> : <AlertTriangle size={18}/>} {item.transfer_ready ? "Transfer ready" : "Recipient missing"}</div></div>) : <Empty text="No payout items in this period."/>}</div></section>
      <section className="card mt-6 overflow-hidden"><header className="flex flex-wrap items-center justify-between gap-4 border-b border-[var(--line)] p-6"><div><div className="eyebrow">Ledger integrity</div><h2 className="mt-2 text-2xl font-bold">Payment reconciliation</h2><p className="mt-1 text-sm text-[var(--muted)]">{mismatchCount} mismatches detected in this period.</p></div><label className="flex items-center gap-3 font-bold"><input type="checkbox" checked={onlyMismatches} onChange={(e) => setOnlyMismatches(e.target.checked)}/>Only show mismatches</label></header><div className="overflow-x-auto"><table className="w-full min-w-[850px] text-left text-sm"><thead className="bg-[var(--blue-pale)] text-xs uppercase text-[var(--muted)]"><tr>{["Request", "Paid", "Fee", "Wage", "Refund", "Payout", "Integrity"].map((h) => <th className="p-4" key={h}>{h}</th>)}</tr></thead><tbody>{reconciliation.map((row) => <tr className="border-t border-[var(--line)]" key={row.booking_request_id}><td className="p-4 font-bold">#{row.booking_request_id}<div className="font-normal capitalize text-[var(--muted)]">{row.status}</div></td><td className="p-4">{money(row.total_paid_cents)}</td><td className="p-4">{money(row.booking_fee_cents)}</td><td className="p-4">{money(row.wage_cents)}</td><td className="p-4">{money(row.refund_cents)}</td><td className="p-4">{money(row.payout_released_cents)}</td><td className="p-4">{row.problems.length ? <span className="font-bold text-red-700">{row.problems.map(label).join(", ")}</span> : <span className="font-bold text-emerald-700">Balanced</span>}</td></tr>)}</tbody></table>{!reconciliation.length && <Empty text="No paid booking ledger entries in this period."/>}</div></section>
    </>}
  </div>;
}

function Loading() { return <div className="flex min-h-64 items-center justify-center"><LoaderCircle className="animate-spin"/></div>; }
function Empty({ text }: { text: string }) { return <div className="p-8 text-center text-[var(--muted)]">{text}</div>; }
function AccessDenied() { return <div className="card mx-auto max-w-xl p-8 text-center"><h1 className="text-2xl font-bold">Team access only</h1></div>; }
