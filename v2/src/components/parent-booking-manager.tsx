"use client";

import { apiJson } from "@/lib/api";
import {
  BadgeCheck,
  CalendarDays,
  Check,
  Clock,
  LoaderCircle,
  MessageSquareWarning,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";

type BookingDay = {
  booking_id: number;
  booking_state?: string;
  status?: string;
  start_dt?: string;
  end_dt?: string;
  check_in_at?: string | null;
  check_in_confirmed_at?: string | null;
  check_out_at?: string | null;
  check_out_confirmed_at?: string | null;
  overrun_minutes?: number | null;
  overrun_amount_cents?: number | null;
  overrun_status?: string | null;
  late_minutes?: number;
  early_departure_minutes?: number;
  billable_minutes?: number | null;
  scheduled_minutes?: number | null;
  service_wage_cents?: number | null;
  service_fee_cents?: number | null;
  service_refund_cents?: number;
  service_adjustment_status?: string | null;
};
type ChargeQuery = {
  id: number;
  booking_id?: number | null;
  line_item: "nanny_wage" | "booking_fee" | "overtime" | "other";
  charge_amount_cents: number;
  disputed_amount_cents: number;
  approved_refund_cents?: number;
  reason: string;
  details?: string | null;
  status: string;
  resolution_reason?: string | null;
  failure_reason?: string | null;
  created_at?: string | null;
};
type ParentBooking = {
  job_id: number;
  status: string;
  booking_state?: string;
  booking_category?: string;
  start_dt?: string;
  end_dt?: string;
  wage_cents?: number;
  booking_fee_cents?: number;
  total_cents?: number;
  accepted_nanny_name?: string | null;
  accepted_nannies?: { name?: string }[];
  requested_nannies_count?: number;
  filled_nannies_count?: number;
  remaining_nannies_count?: number;
  estimated_group_total_cents?: number;
  requested_nannies?: { name?: string; response_status?: string }[];
  booking_days?: BookingDay[];
  booking_form?: Record<string, unknown>;
  payment_status?: string | null;
  charge_disputes?: ChargeQuery[];
};

const stateLabels: Record<string, string> = {
  awaiting_acceptance: "Awaiting nanny",
  broadcast_sent: "Requested",
  awaiting_payment: "Awaiting payment",
  confirmed: "Confirmed",
  in_progress: "In progress",
  completed: "Completed",
  past: "Past",
  cancelled: "Cancelled",
  admin_review: "Admin review",
  awaiting_overtime_approval: "Overtime approval",
};
const chargeQueryStatusLabels: Record<string, string> = {
  open: "Finance review",
  refund_requested: "Refund processing",
  refunded: "Refund completed",
  denied: "Not approved",
  failed: "Needs finance attention",
};
const activeChargeQueryStatuses = new Set(["open", "refund_requested", "failed"]);

function dateTime(value?: string) {
  if (!value) return "Not scheduled";
  return new Date(value).toLocaleString("en-ZA", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}
function money(value?: number | null) {
  return `R${((value || 0) / 100).toFixed(2)}`;
}

export function ParentBookingManager() {
  const [rows, setRows] = useState<ParentBooking[]>([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [filter, setFilter] = useState("current");
  const [busy, setBusy] = useState("");
  const [queryJobId, setQueryJobId] = useState<number | null>(null);
  const [queryLineItem, setQueryLineItem] = useState<ChargeQuery["line_item"]>("nanny_wage");
  const [queryBookingId, setQueryBookingId] = useState("");
  const [queryAmount, setQueryAmount] = useState("");
  const [queryReason, setQueryReason] = useState("");
  const [queryDetails, setQueryDetails] = useState("");
  async function correctTime(day: BookingDay, kind: "in" | "out") {
    const current = kind === "in" ? day.check_in_at : day.check_out_at;
    const corrected = window.prompt(
      `Enter the correct ${kind === "in" ? "arrival" : "finish"} time in ISO format`,
      current || "",
    );
    if (!corrected?.trim()) return;
    await action(
      `correct-${kind}-${day.booking_id}`,
      `/parents/me/bookings/${day.booking_id}/confirm-check-${kind}`,
      { confirmed: false, corrected_time: corrected.trim() },
    );
  }
  async function disputeTime(day: BookingDay, kind: "in" | "out") {
    if (!window.confirm(`Dispute this ${kind === "in" ? "arrival" : "finish"} time and send it to My Nanny for review?`)) return;
    await action(
      `dispute-${kind}-${day.booking_id}`,
      `/parents/me/bookings/${day.booking_id}/confirm-check-${kind}`,
      { confirmed: false },
    );
  }
  async function load() {
    setLoading(true);
    try {
      const data = await apiJson<{ results?: ParentBooking[] } | ParentBooking[]>(
        "/parents/me/booking-requests",
      );
      setRows(Array.isArray(data) ? data : data.results || []);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to load bookings.");
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, []);
  async function action(key: string, path: string, body?: unknown) {
    setBusy(key);
    setMessage("");
    try {
      await apiJson(path, {
        method: path.includes("/cancel") ? "PATCH" : "POST",
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      await load();
      setMessage("Booking updated successfully.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to update booking.");
    } finally {
      setBusy("");
    }
  }
  function cancel(jobId: number) {
    const reason = window.prompt("Why are you cancelling this booking?");
    if (!reason?.trim()) return;
    void action(
      `cancel-${jobId}`,
      `/parents/me/booking-requests/${jobId}/cancel`,
      { reason: reason.trim() },
    );
  }
  function openChargeQuery(booking: ParentBooking) {
    setQueryJobId(booking.job_id);
    setQueryLineItem("nanny_wage");
    setQueryBookingId("");
    setQueryAmount(((booking.wage_cents || 0) / 100).toFixed(2));
    setQueryReason("");
    setQueryDetails("");
  }
  function changeQueryLine(booking: ParentBooking, lineItem: ChargeQuery["line_item"]) {
    setQueryLineItem(lineItem);
    if (lineItem !== "overtime") setQueryBookingId("");
    const amount = lineItem === "nanny_wage"
      ? booking.wage_cents
      : lineItem === "booking_fee"
        ? booking.booking_fee_cents
        : lineItem === "other"
          ? booking.total_cents
          : 0;
    setQueryAmount(amount ? (amount / 100).toFixed(2) : "");
  }
  async function submitChargeQuery(booking: ParentBooking) {
    const amountCents = Math.round(Number(queryAmount) * 100);
    if (!Number.isFinite(amountCents) || amountCents < 1) {
      setMessage("Enter the amount you want finance to review.");
      return;
    }
    if (queryReason.trim().length < 3) {
      setMessage("Please briefly explain why you are querying this charge.");
      return;
    }
    if (queryLineItem === "overtime" && !queryBookingId) {
      setMessage("Choose the booking day linked to the overtime charge.");
      return;
    }
    setBusy(`charge-query-${booking.job_id}`);
    setMessage("");
    try {
      await apiJson(`/parents/me/booking-requests/${booking.job_id}/charge-disputes`, {
        method: "POST",
        body: JSON.stringify({
          line_item: queryLineItem,
          booking_id: queryBookingId ? Number(queryBookingId) : null,
          amount_cents: amountCents,
          reason: queryReason.trim(),
          details: queryDetails.trim() || null,
        }),
      });
      setQueryJobId(null);
      await load();
      setMessage("Your charge query has been sent to the finance team. The related nanny payout is on hold while it is reviewed.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to submit this charge query.");
    } finally {
      setBusy("");
    }
  }
  const visible = rows.filter((row) => {
    const state = row.booking_state || row.status;
    if (filter === "past")
      return ["completed", "past", "cancelled", "rejected"].includes(state);
    return !["completed", "past", "cancelled", "rejected"].includes(state);
  });
  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="eyebrow">Your care schedule</div>
          <h1 className="display mt-2 text-4xl sm:text-5xl">Manage bookings.</h1>
          <p className="mt-3 text-[var(--muted)]">
            Track nanny responses, confirmed care, attendance and payments.
          </p>
        </div>
        <div className="flex rounded-full bg-slate-100 p-1">
          {["current", "past"].map((value) => (
            <button
              key={value}
              onClick={() => setFilter(value)}
              className={`rounded-full px-4 py-2 text-sm font-bold capitalize ${filter === value ? "bg-white shadow-sm" : "text-[var(--muted)]"}`}
            >
              {value}
            </button>
          ))}
        </div>
      </div>
      {message && (
        <div className="mt-5 rounded-xl bg-[var(--blue-pale)] p-4 text-sm">{message}</div>
      )}
      {loading ? (
        <div className="mt-12 flex justify-center"><LoaderCircle className="animate-spin" /></div>
      ) : visible.length ? (
        <div className="mt-7 grid gap-5">
          {visible.map((booking) => (
            <article className="card overflow-hidden" key={booking.job_id}>
              <div className="flex flex-wrap items-start justify-between gap-4 bg-[linear-gradient(135deg,var(--blue-pale),#fff)] p-6">
                <div>
                  <div className="text-xs font-extrabold uppercase tracking-widest text-[var(--blue-dark)]">Booking #{booking.job_id}</div>
                  <h2 className="mt-2 text-2xl font-bold">{booking.accepted_nannies?.length ? booking.accepted_nannies.map((nanny) => nanny.name).join(", ") : booking.accepted_nanny_name || "Finding your nanny"}</h2>
                  <div className="mt-2 text-sm font-semibold text-[var(--blue-dark)]">{booking.filled_nannies_count || 0} of {booking.requested_nannies_count || 1} nanny positions filled</div>
                  <div className="mt-2 flex items-center gap-2 text-sm text-[var(--muted)]"><CalendarDays size={16} />{dateTime(booking.start_dt)} to {dateTime(booking.end_dt)}</div>
                </div>
                <span className="pill !bg-white">{stateLabels[booking.booking_state || booking.status] || (booking.booking_state || booking.status).replaceAll("_", " ")}</span>
              </div>
              <div className="grid gap-5 p-6 lg:grid-cols-[1fr_.72fr]">
                <div className="grid gap-3">
                  {(booking.booking_days || []).map((day) => (
                    <div className="rounded-2xl border border-[var(--line)] p-4" key={day.booking_id}>
                      <div className="flex flex-wrap justify-between gap-3">
                        <b>{dateTime(day.start_dt)}</b>
                        <span className="text-sm text-[var(--muted)]">{stateLabels[day.booking_state || ""] || day.booking_state}</span>
                      </div>
                      <div className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                        <span><Clock size={14} className="mr-2 inline" />Arrival: {day.check_in_at ? dateTime(day.check_in_at) : "Not reported"}</span>
                        <span><Clock size={14} className="mr-2 inline" />Finish: {day.check_out_at ? dateTime(day.check_out_at) : "Not reported"}</span>
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {day.check_in_at && !day.check_in_confirmed_at && (
                          <><button className="btn-secondary !min-h-9" disabled={busy === `in-${day.booking_id}`} onClick={() => void action(`in-${day.booking_id}`, `/parents/me/bookings/${day.booking_id}/confirm-check-in`, { confirmed: true })}><Check size={15} />Confirm arrival</button><button className="btn-quiet !min-h-9" onClick={() => void correctTime(day, "in")}>Correct</button><button className="btn-quiet !min-h-9 text-red-700" onClick={() => void disputeTime(day, "in")}>Dispute</button></>
                        )}
                        {day.check_out_at && !day.check_out_confirmed_at && (
                          <><button className="btn-secondary !min-h-9" disabled={busy === `out-${day.booking_id}`} onClick={() => void action(`out-${day.booking_id}`, `/parents/me/bookings/${day.booking_id}/confirm-check-out`, { confirmed: true })}><Check size={15} />Confirm finish</button><button className="btn-quiet !min-h-9" onClick={() => void correctTime(day, "out")}>Correct</button><button className="btn-quiet !min-h-9 text-red-700" onClick={() => void disputeTime(day, "out")}>Dispute</button></>
                        )}
                        {day.overrun_status === "awaiting_parent" && (
                          <>
                            <button className="btn-primary !min-h-9" onClick={() => void action(`ot-${day.booking_id}`, `/bookings/${day.booking_id}/overtime/agree`)}>Approve {money(day.overrun_amount_cents)}</button>
                            <button className="btn-secondary !min-h-9" onClick={() => void action(`query-${day.booking_id}`, `/bookings/${day.booking_id}/overtime/query`)}>Query overtime</button>
                          </>
                        )}
                      </div>
                      {(day.late_minutes || day.early_departure_minutes || day.service_refund_cents) ? <div className="mt-3 rounded-xl bg-amber-50 p-3 text-sm text-amber-950"><b>Service adjustment</b><div className="mt-1">{day.late_minutes || 0} min late · {day.early_departure_minutes || 0} min early · {money(day.service_refund_cents)} due back to you</div><div className="mt-1 text-xs capitalize">{(day.service_adjustment_status || "Awaiting time confirmation").replaceAll("_", " ")}</div></div> : null}
                    </div>
                  ))}
                  {!booking.booking_days?.length && (
                    <div className="rounded-2xl bg-slate-50 p-4 text-sm text-[var(--muted)]">Waiting for confirmation. Requested nannies: {booking.requested_nannies?.map((nanny) => `${nanny.name} (${nanny.response_status || "pending"})`).join(", ") || "one selected nanny"}.</div>
                  )}
                </div>
                <aside className="rounded-2xl bg-slate-50 p-5">
                  <h3 className="font-bold">Rates & payment</h3>
                  <div className="mt-4 grid gap-3 text-sm">
                    <div className="flex justify-between"><span>Nanny wage</span><b>{money(booking.wage_cents)}</b></div>
                    <div className="flex justify-between"><span>Booking fee</span><b>{money(booking.booking_fee_cents)}</b></div>
                    <div className="flex justify-between border-t border-[var(--line)] pt-3 text-base"><span>Estimated total</span><b>{money(booking.estimated_group_total_cents ?? booking.total_cents)}</b></div>
                  </div>
                  {(booking.charge_disputes || []).length > 0 && (
                    <div className="mt-5 border-t border-[var(--line)] pt-4">
                      <h4 className="text-sm font-bold">Charge queries</h4>
                      <div className="mt-3 grid gap-2">
                        {(booking.charge_disputes || []).map((query) => (
                          <div className="rounded-xl bg-white p-3 text-xs" key={query.id}>
                            <div className="flex items-start justify-between gap-3">
                              <b className="capitalize">{query.line_item.replaceAll("_", " ")}</b>
                              <span className="pill !min-h-0 !px-2 !py-1 text-[10px]">{chargeQueryStatusLabels[query.status] || query.status.replaceAll("_", " ")}</span>
                            </div>
                            <div className="mt-2">Queried: <b>{money(query.disputed_amount_cents)}</b>{query.approved_refund_cents ? <> · Refund: <b>{money(query.approved_refund_cents)}</b></> : null}</div>
                            <p className="mt-1 text-[var(--muted)]">{query.reason}</p>
                            {query.resolution_reason && <p className="mt-1"><b>Finance:</b> {query.resolution_reason}</p>}
                            {query.failure_reason && <p className="mt-1 text-red-700"><b>Processing issue:</b> {query.failure_reason}</p>}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {booking.payment_status === "paid" && !(booking.charge_disputes || []).some((query) => activeChargeQueryStatuses.has(query.status)) && queryJobId !== booking.job_id && (
                    <button className="btn-secondary mt-5 w-full" onClick={() => openChargeQuery(booking)}><MessageSquareWarning size={16} />Query this charge</button>
                  )}
                  {queryJobId === booking.job_id && (
                    <div className="mt-5 border-t border-[var(--line)] pt-4">
                      <div className="flex items-start justify-between gap-3">
                        <div><h4 className="font-bold">Query a charge</h4><p className="mt-1 text-xs text-[var(--muted)]">Finance can approve a full or partial refund. The related payout is held during review.</p></div>
                        <button className="btn-quiet !min-h-8 !px-2" onClick={() => setQueryJobId(null)} aria-label="Close charge query"><X size={16} /></button>
                      </div>
                      <label className="mt-4 block text-xs font-bold">Charge</label>
                      <select className="field mt-2" value={queryLineItem} onChange={(event) => changeQueryLine(booking, event.target.value as ChargeQuery["line_item"])}>
                        <option value="nanny_wage">Nanny wage</option>
                        <option value="booking_fee">Booking fee</option>
                        <option value="overtime">Overtime</option>
                        <option value="other">Another part of the total</option>
                      </select>
                      {queryLineItem === "overtime" && (
                        <><label className="mt-3 block text-xs font-bold">Booking day</label><select className="field mt-2" value={queryBookingId} onChange={(event) => setQueryBookingId(event.target.value)}><option value="">Choose a day</option>{(booking.booking_days || []).map((day) => <option key={day.booking_id} value={day.booking_id}>{dateTime(day.start_dt)} · {money(day.overrun_amount_cents)}</option>)}</select></>
                      )}
                      <label className="mt-3 block text-xs font-bold">Amount to review</label>
                      <div className="relative mt-2"><span className="absolute left-4 top-1/2 -translate-y-1/2 font-bold">R</span><input className="field !pl-9" inputMode="decimal" min="0.01" step="0.01" type="number" value={queryAmount} onChange={(event) => setQueryAmount(event.target.value)} /></div>
                      <label className="mt-3 block text-xs font-bold">Reason</label>
                      <input className="field mt-2" maxLength={200} placeholder="For example: nanny arrived late" value={queryReason} onChange={(event) => setQueryReason(event.target.value)} />
                      <label className="mt-3 block text-xs font-bold">More detail <span className="font-normal text-[var(--muted)]">(optional)</span></label>
                      <textarea className="field mt-2 min-h-24 resize-y" maxLength={2000} placeholder="Tell our finance team what happened." value={queryDetails} onChange={(event) => setQueryDetails(event.target.value)} />
                      <button className="btn-primary mt-4 w-full" disabled={busy === `charge-query-${booking.job_id}`} onClick={() => void submitChargeQuery(booking)}>{busy === `charge-query-${booking.job_id}` ? <LoaderCircle className="animate-spin" size={16} /> : <MessageSquareWarning size={16} />}Send to finance</button>
                    </div>
                  )}
                  {!['completed','past','cancelled','rejected'].includes(booking.booking_state || booking.status) && (
                    <button className="btn-quiet mt-5 text-red-700" disabled={busy === `cancel-${booking.job_id}`} onClick={() => cancel(booking.job_id)}><X size={16} />Cancel booking</button>
                  )}
                </aside>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="card mt-7 p-10 text-center">
          <BadgeCheck className="mx-auto text-[var(--green)]" size={36} />
          <h2 className="mt-4 text-xl font-bold">No {filter} bookings</h2>
          <p className="mt-2 text-[var(--muted)]">Your booking activity will appear here.</p>
        </div>
      )}
    </div>
  );
}
