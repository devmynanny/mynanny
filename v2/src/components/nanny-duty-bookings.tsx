"use client";

import { apiJson } from "@/lib/api";
import { CalendarDays, Clock, LoaderCircle, MapPin, Phone, Wallet, X } from "lucide-react";
import { useEffect, useState } from "react";

type Duty = {
  booking_id: number;
  booking_request_id?: number | null;
  booking_state?: string;
  status?: string;
  parent_name: string;
  parent_phone?: string | null;
  start_dt?: string;
  end_dt?: string;
  location_label?: string | null;
  location_address?: string | null;
  check_in_at?: string | null;
  check_out_at?: string | null;
  check_in_distance_m?: number | null;
  check_out_distance_m?: number | null;
  wage_cents?: number;
  daily_wage_cents?: number;
};

function when(value?: string) {
  return value
    ? new Date(value).toLocaleString("en-ZA", { dateStyle: "medium", timeStyle: "short" })
    : "Not scheduled";
}

export function NannyDutyBookings() {
  const [rows, setRows] = useState<Duty[]>([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(0);
  const [filter, setFilter] = useState<"upcoming" | "past">("upcoming");
  async function load() {
    setLoading(true);
    try {
      const data = await apiJson<{ results: Duty[] }>("/nannies/me/duty-bookings");
      setRows(data.results || []);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to load duty bookings.");
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, []);
  function dutyAction(bookingId: number, action: "check-in" | "check-out") {
    if (!navigator.geolocation) {
      setMessage("Location services are unavailable in this browser.");
      return;
    }
    setBusy(bookingId);
    setMessage("Checking your location...");
    navigator.geolocation.getCurrentPosition(
      async ({ coords }) => {
        try {
          await apiJson(`/nannies/me/bookings/${bookingId}/${action}`, {
            method: "POST",
            body: JSON.stringify({ lat: coords.latitude, lng: coords.longitude }),
          });
          await load();
          setMessage(action === "check-in" ? "You are checked in." : "You are checked out.");
        } catch (error) {
          setMessage(error instanceof Error ? error.message : `Unable to ${action}.`);
        } finally {
          setBusy(0);
        }
      },
      () => { setBusy(0); setMessage("Allow precise location access and try again."); },
      { enableHighAccuracy: true, timeout: 15000 },
    );
  }
  async function cancel(row: Duty) {
    const reason = window.prompt("Why do you need to cancel this booking?");
    if (!reason?.trim()) return;
    setBusy(row.booking_id);
    try {
      await apiJson(`/nannies/me/bookings/${row.booking_id}/cancel`, {
        method: "POST",
        body: JSON.stringify({ reason: reason.trim() }),
      });
      await load();
      setMessage("Booking cancelled. The My Nanny team has been notified.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to cancel booking.");
    } finally { setBusy(0); }
  }
  const visible = rows.filter((row) => {
    const past = ["completed", "past", "cancelled"].includes(
      row.booking_state || row.status || "",
    );
    return filter === "past" ? past : !past;
  });
  return (
    <div className="mx-auto max-w-6xl">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div><div className="eyebrow">Your schedule</div><h1 className="display mt-2 text-4xl sm:text-5xl">Duty bookings.</h1><p className="mt-3 text-[var(--muted)]">Everything you need before, during and after a booking.</p></div>
        <div className="flex rounded-full bg-slate-100 p-1">{(["upcoming", "past"] as const).map((value) => <button key={value} className={`rounded-full px-4 py-2 text-sm font-bold capitalize ${filter === value ? "bg-white shadow-sm" : "text-[var(--muted)]"}`} onClick={() => setFilter(value)}>{value}</button>)}</div>
      </div>
      {message && <div className="mt-5 rounded-xl bg-[var(--blue-pale)] p-4 text-sm">{message}</div>}
      {loading ? <div className="mt-12 flex justify-center"><LoaderCircle className="animate-spin" /></div> : visible.length ? (
        <div className="mt-7 grid gap-5 md:grid-cols-2">
          {visible.map((row) => (
            <article className="card overflow-hidden" key={row.booking_id}>
              <div className="bg-[var(--blue-dark)] p-6 text-white"><div className="flex justify-between gap-3"><span className="text-xs font-extrabold uppercase tracking-widest text-white/60">Booking #{row.booking_id}</span><span className="pill !border-white/20 !bg-white/10 !text-white capitalize">{(row.booking_state || row.status || "confirmed").replaceAll("_", " ")}</span></div><h2 className="mt-4 text-2xl font-bold">{row.parent_name}</h2><div className="mt-3 flex items-center gap-2 text-sm text-white/70"><CalendarDays size={16} />{when(row.start_dt)} to {when(row.end_dt)}</div></div>
              <div className="grid gap-4 p-6 text-sm">
                <div className="flex gap-3"><MapPin className="shrink-0 text-[var(--coral)]" size={18} /><span><b className="block">Booking location</b>{row.location_address || row.location_label || "Location pending"}</span></div>
                {row.parent_phone && <a href={`tel:${row.parent_phone}`} className="flex gap-3"><Phone size={18} /><span><b className="block">Parent telephone</b>{row.parent_phone}</span></a>}
                <div className="flex gap-3"><Wallet size={18} /><span><b className="block">Expected earnings</b>R{((row.daily_wage_cents || row.wage_cents || 0) / 100).toFixed(2)}</span></div>
                <div className="rounded-2xl bg-slate-50 p-4"><div><Clock size={15} className="mr-2 inline" />Checked in: {row.check_in_at ? when(row.check_in_at) : "Not yet"}</div><div className="mt-2"><Clock size={15} className="mr-2 inline" />Checked out: {row.check_out_at ? when(row.check_out_at) : "Not yet"}</div></div>
                {!row.check_in_at && filter === "upcoming" && <button className="btn-primary" disabled={busy === row.booking_id} onClick={() => dutyAction(row.booking_id, "check-in")}>{busy === row.booking_id ? <LoaderCircle className="animate-spin" size={17} /> : <MapPin size={17} />}Check in</button>}
                {row.check_in_at && !row.check_out_at && <button className="btn-primary" disabled={busy === row.booking_id} onClick={() => dutyAction(row.booking_id, "check-out")}>{busy === row.booking_id ? <LoaderCircle className="animate-spin" size={17} /> : <MapPin size={17} />}Check out</button>}
                {!['completed','past','cancelled'].includes(row.booking_state || row.status || "") && <button className="btn-quiet text-red-700" onClick={() => void cancel(row)}><X size={16} />Cancel booking</button>}
              </div>
            </article>
          ))}
        </div>
      ) : <div className="card mt-7 p-10 text-center text-[var(--muted)]">No {filter} duty bookings.</div>}
    </div>
  );
}
