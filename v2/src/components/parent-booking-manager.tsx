"use client";

import { apiJson } from "@/lib/api";
import {
  BadgeCheck,
  CalendarDays,
  Check,
  Clock,
  LoaderCircle,
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
