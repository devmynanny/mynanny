"use client";

import { AuthenticatedPage } from "@/components/authenticated-page";
import { apiJson } from "@/lib/api";
import { Check, CircleDollarSign, LoaderCircle, MessageSquareWarning, RefreshCw, Undo2, X } from "lucide-react";
import { useEffect, useEffectEvent, useState, type ReactNode } from "react";

type Refund = {
  job_id: number;
  request_id: number;
  status: string;
  refund_status?: string | null;
  refund_cents?: number | null;
  parent_user_id: number;
  nanny_id?: number | null;
  created_at?: string | null;
};

type ChargeQuery = {
  id: number;
  job_id?: number | null;
  booking_request_id: number;
  booking_id?: number | null;
  parent_user_id: number;
  parent_name?: string | null;
  parent_email?: string | null;
  nanny_id?: number | null;
  nanny_name?: string | null;
  starts_at?: string | null;
  line_item: string;
  charge_amount_cents: number;
  disputed_amount_cents: number;
  approved_refund_cents: number;
  reason: string;
  details?: string | null;
  status: string;
  resolution_reason?: string | null;
  failure_reason?: string | null;
  paystack_refund_reference?: string | null;
  created_at?: string | null;
};

type Queue = "charge_queries" | "cancellations";

const money = (value?: number | null) =>
  `R${(Number(value || 0) / 100).toLocaleString("en-ZA", { minimumFractionDigits: 2 })}`;

const dateTime = (value?: string | null) =>
  value
    ? new Date(value).toLocaleString("en-ZA", {
        dateStyle: "medium",
        timeStyle: "short",
        timeZone: "Africa/Johannesburg",
      })
    : "Not available";

const statusLabels: Record<string, string> = {
  open: "Awaiting finance review",
  refund_requested: "Paystack processing",
  refunded: "Refund completed",
  denied: "Not approved",
  failed: "Processing failed",
};

export default function RefundsPage() {
  return (
    <AuthenticatedPage>
      {(role) =>
        role === "admin" ? (
          <Refunds />
        ) : (
          <div className="card mx-auto max-w-xl p-8 text-center">
            <h1 className="text-2xl font-bold">Team access only</h1>
          </div>
        )
      }
    </AuthenticatedPage>
  );
}

function Refunds() {
  const [queue, setQueue] = useState<Queue>("charge_queries");
  const [queryFilter, setQueryFilter] = useState("open");
  const [refundFilter, setRefundFilter] = useState("pending_review");
  const [queries, setQueries] = useState<ChargeQuery[]>([]);
  const [refunds, setRefunds] = useState<Refund[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<number | null>(null);
  const [reviewing, setReviewing] = useState<number | null>(null);
  const [reviewAmount, setReviewAmount] = useState("");
  const [reviewReason, setReviewReason] = useState("");
  const [message, setMessage] = useState("");

  async function load() {
    setLoading(true);
    setMessage("");
    try {
      if (queue === "charge_queries") {
        const data = await apiJson<{ results: ChargeQuery[] }>(`/admin/charge-disputes?status=${queryFilter}`);
        setQueries(data.results || []);
      } else {
        const data = await apiJson<{ results: Refund[] }>(`/admin/refunds?status=${refundFilter}`);
        setRefunds(data.results || []);
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to load finance activity.");
    } finally {
      setLoading(false);
    }
  }

  const loadForFilter = useEffectEvent(load);
  useEffect(() => {
    Promise.resolve().then(() => loadForFilter());
  }, [queue, queryFilter, refundFilter]);

  function beginReview(query: ChargeQuery) {
    setReviewing(query.id);
    setReviewAmount((query.disputed_amount_cents / 100).toFixed(2));
    setReviewReason("");
    setMessage("");
  }

  async function decideQuery(query: ChargeQuery, decision: "approve" | "deny") {
    if (!reviewReason.trim()) {
      setMessage("Add a finance decision reason before continuing.");
      return;
    }
    const amountCents = Math.round(Number(reviewAmount) * 100);
    if (decision === "approve" && (!Number.isFinite(amountCents) || amountCents < 1)) {
      setMessage("Enter a valid refund amount.");
      return;
    }
    setBusy(query.id);
    setMessage("");
    try {
      await apiJson(`/admin/charge-disputes/${query.id}/${decision}`, {
        method: "POST",
        body: JSON.stringify({
          amount_cents: decision === "approve" ? amountCents : null,
          reason: reviewReason.trim(),
        }),
      });
      setReviewing(null);
      setReviewAmount("");
      setReviewReason("");
      setMessage(
        decision === "approve"
          ? "Refund sent to Paystack for processing. It is not marked complete until Paystack confirms it."
          : "Charge query declined and the related nanny payout hold has been released.",
      );
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to update this charge query.");
    } finally {
      setBusy(null);
    }
  }

  async function decideCancellation(row: Refund, decision: "approve" | "deny") {
    const reason = window.prompt(
      decision === "approve"
        ? `Approve the ${money(row.refund_cents)} cancellation refund for booking #${row.job_id}? Add an internal reason:`
        : `Why is the cancellation refund for booking #${row.job_id} being declined?`,
      "",
    );
    if (reason === null || !reason.trim()) return;
    setBusy(row.job_id);
    setMessage("");
    try {
      await apiJson(`/admin/booking-requests/${row.job_id}/refund/${decision}`, {
        method: "POST",
        body: JSON.stringify({ reason: reason.trim() }),
      });
      setMessage(`Cancellation refund ${decision === "approve" ? "approved" : "declined"}.`);
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to update this refund.");
    } finally {
      setBusy(null);
    }
  }

  const count = queue === "charge_queries" ? queries.length : refunds.length;

  return (
    <div className="mx-auto max-w-6xl">
      <div className="eyebrow">Payment operations</div>
      <div className="mt-2 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="display text-4xl sm:text-5xl">Queries & refunds.</h1>
          <p className="mt-3 max-w-2xl text-[var(--muted)]">
            Review a client&apos;s specific charge, approve a controlled partial refund, and track Paystack completion separately from the finance decision.
          </p>
        </div>
        <button className="btn-secondary" onClick={() => void load()}><RefreshCw size={17} />Refresh</button>
      </div>

      <div className="mt-7 flex w-fit max-w-full gap-1 overflow-x-auto rounded-full bg-slate-100 p-1">
        <QueueButton active={queue === "charge_queries"} onClick={() => setQueue("charge_queries")}>Charge queries</QueueButton>
        <QueueButton active={queue === "cancellations"} onClick={() => setQueue("cancellations")}>Cancellation refunds</QueueButton>
      </div>

      <div className="card mt-5 flex flex-wrap items-center justify-between gap-4 p-4">
        <div className="flex items-center gap-3">
          <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[var(--blue-pale)] text-[var(--blue-dark)]">
            {queue === "charge_queries" ? <MessageSquareWarning /> : <Undo2 />}
          </span>
          <b>{count} records</b>
        </div>
        {queue === "charge_queries" ? (
          <select className="field max-w-64" value={queryFilter} onChange={(event) => setQueryFilter(event.target.value)}>
            <option value="open">Awaiting finance review</option>
            <option value="refund_requested">Paystack processing</option>
            <option value="refunded">Refund completed</option>
            <option value="denied">Not approved</option>
            <option value="failed">Processing failed</option>
            <option value="all">All charge queries</option>
          </select>
        ) : (
          <select className="field max-w-56" value={refundFilter} onChange={(event) => setRefundFilter(event.target.value)}>
            <option value="pending_review">Awaiting review</option>
            <option value="processed">Processed</option>
            <option value="denied">Declined</option>
            <option value="failed">Failed</option>
            <option value="all">All paid bookings</option>
          </select>
        )}
      </div>

      {message && <div className="mt-5 rounded-2xl bg-[var(--blue-pale)] p-4 font-semibold">{message}</div>}

      <section className="card mt-6 overflow-hidden">
        {loading ? (
          <div className="flex min-h-64 items-center justify-center"><LoaderCircle className="animate-spin" /></div>
        ) : queue === "charge_queries" ? (
          queries.length ? (
            <div className="divide-y divide-[var(--line)]">
              {queries.map((query) => (
                <article className="p-6" key={query.id}>
                  <div className="grid gap-5 lg:grid-cols-[1fr_auto]">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <h2 className="text-xl font-bold">Booking #{query.job_id || query.booking_request_id}</h2>
                        <span className="pill">{statusLabels[query.status] || query.status.replaceAll("_", " ")}</span>
                      </div>
                      <div className="mt-4 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
                        <span>Client <b className="block">{query.parent_name || `#${query.parent_user_id}`}</b></span>
                        <span>Nanny <b className="block">{query.nanny_name || "Not assigned"}</b></span>
                        <span>Charge <b className="block capitalize">{query.line_item.replaceAll("_", " ")}</b></span>
                        <span>Care date <b className="block">{dateTime(query.starts_at)}</b></span>
                      </div>
                      <div className="mt-4 flex flex-wrap gap-x-6 gap-y-2 rounded-2xl bg-slate-50 p-4 text-sm">
                        <span>Original charge <b>{money(query.charge_amount_cents)}</b></span>
                        <span>Client queried <b>{money(query.disputed_amount_cents)}</b></span>
                        {query.approved_refund_cents > 0 && <span>Approved refund <b>{money(query.approved_refund_cents)}</b></span>}
                      </div>
                      <div className="mt-4 text-sm"><b>Client reason:</b> {query.reason}</div>
                      {query.details && <p className="mt-2 text-sm text-[var(--muted)]">{query.details}</p>}
                      {query.resolution_reason && <p className="mt-3 text-sm"><b>Finance decision:</b> {query.resolution_reason}</p>}
                      {query.failure_reason && <p className="mt-3 rounded-xl bg-red-50 p-3 text-sm text-red-800"><b>Paystack error:</b> {query.failure_reason}</p>}
                      <p className="mt-3 text-xs text-[var(--muted)]">Submitted {dateTime(query.created_at)}{query.paystack_refund_reference ? ` · Paystack refund ${query.paystack_refund_reference}` : ""}</p>
                    </div>
                    {(query.status === "open" || query.status === "failed") && reviewing !== query.id && (
                      <button className="btn-primary self-start" onClick={() => beginReview(query)}><CircleDollarSign size={17} />Review query</button>
                    )}
                  </div>

                  {reviewing === query.id && (
                    <div className="mt-5 rounded-2xl border border-[var(--line)] bg-[var(--blue-pale)] p-5">
                      <div className="flex items-start justify-between gap-4">
                        <div><h3 className="font-bold">Finance decision</h3><p className="mt-1 text-xs text-[var(--muted)]">A partial refund cannot exceed {money(Math.min(query.disputed_amount_cents, query.charge_amount_cents))}.</p></div>
                        <button className="btn-quiet !min-h-8 !px-2" onClick={() => setReviewing(null)} aria-label="Close finance review"><X size={17} /></button>
                      </div>
                      <div className="mt-4 grid gap-4 sm:grid-cols-[.45fr_1fr]">
                        <label className="text-sm font-bold">Refund amount<input className="field mt-2" type="number" min="0.01" step="0.01" value={reviewAmount} onChange={(event) => setReviewAmount(event.target.value)} /></label>
                        <label className="text-sm font-bold">Decision reason<input className="field mt-2" maxLength={500} placeholder="Required for the audit trail and client notification" value={reviewReason} onChange={(event) => setReviewReason(event.target.value)} /></label>
                      </div>
                      <div className="mt-4 flex flex-wrap gap-3">
                        <button className="btn-primary" disabled={busy === query.id} onClick={() => void decideQuery(query, "approve")}>{busy === query.id ? <LoaderCircle className="animate-spin" size={17} /> : <Check size={17} />}Approve partial refund</button>
                        <button className="btn-secondary text-red-700" disabled={busy === query.id} onClick={() => void decideQuery(query, "deny")}><X size={17} />Decline query</button>
                      </div>
                    </div>
                  )}
                </article>
              ))}
            </div>
          ) : <EmptyQueue title="No charge queries in this queue" />
        ) : refunds.length ? (
          <div className="divide-y divide-[var(--line)]">
            {refunds.map((row) => (
              <article className="grid gap-5 p-6 sm:grid-cols-[1fr_auto]" key={row.request_id}>
                <div>
                  <div className="flex flex-wrap items-center gap-2"><h2 className="text-xl font-bold">Booking #{row.job_id}</h2><span className="pill capitalize">{(row.refund_status || "Not requested").replaceAll("_", " ")}</span></div>
                  <div className="mt-3 grid gap-2 text-sm sm:grid-cols-3"><span>Refund <b>{money(row.refund_cents)}</b></span><span>Parent <b>#{row.parent_user_id}</b></span><span>Request <b>#{row.request_id}</b></span></div>
                  <p className="mt-3 text-xs text-[var(--muted)]">Requested {dateTime(row.created_at)}</p>
                </div>
                {row.refund_status === "pending_review" && (
                  <div className="flex flex-wrap items-center gap-2"><button className="btn-primary" disabled={busy === row.job_id} onClick={() => void decideCancellation(row, "approve")}><Check size={17} />Approve refund</button><button className="btn-secondary text-red-700" disabled={busy === row.job_id} onClick={() => void decideCancellation(row, "deny")}><X size={17} />Decline</button></div>
                )}
              </article>
            ))}
          </div>
        ) : <EmptyQueue title="No cancellation refunds in this queue" />}
      </section>
    </div>
  );
}

function QueueButton({ active, children, onClick }: { active: boolean; children: ReactNode; onClick: () => void }) {
  return <button className={`whitespace-nowrap rounded-full px-5 py-3 text-sm font-bold ${active ? "bg-white shadow-sm" : "text-[var(--muted)]"}`} onClick={onClick}>{children}</button>;
}

function EmptyQueue({ title }: { title: string }) {
  return <div className="p-12 text-center"><Check className="mx-auto text-emerald-600" size={34} /><h2 className="mt-4 text-xl font-bold">{title}</h2><p className="mt-2 text-[var(--muted)]">There is nothing requiring action for this filter.</p></div>;
}
