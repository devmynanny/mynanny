"use client";

import { AuthenticatedPage } from "@/components/authenticated-page";
import { MonthCalendar } from "@/components/month-calendar";
import { apiJson } from "@/lib/api";
import { ParentBookingManager } from "@/components/parent-booking-manager";
import { NannyDutyBookings } from "@/components/nanny-duty-bookings";
import {
  ArrowLeft,
  ArrowUpRight,
  CalendarDays,
  CheckCircle2,
  Clock,
  LoaderCircle,
  MapPin,
  MessageCircle,
  Phone,
  ShieldAlert,
  UserRoundPlus,
  UserRound,
  Wallet,
  X,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

type Location = {
  id: number;
  label?: string;
  formatted_address?: string;
  is_default: boolean;
  lat?: number | null;
  lng?: number | null;
};
type BookingResponse = {
  booking_request_id?: number;
  requires_payment_method?: boolean;
  message?: string;
};
type BookingEstimate = {
  currency: string;
  per_nanny_total_cents: number;
  per_nanny_wage_cents: number;
  per_nanny_fee_cents: number;
  booking_fee_pct: number;
  selected_total_cents: number;
};
type PaymentMethod = {
  has_card: boolean;
  card_brand?: string | null;
  card_last4?: string | null;
};
export type OperationsBooking = {
  source: string;
  request_id?: number | null;
  booking_id?: number | null;
  status?: string;
  booking_state?: string;
  parent_name: string;
  parent_email?: string;
  parent_user_id?: number;
  parent_phone?: string | null;
  parent_preferred_channel?: string | null;
  nanny_name: string;
  start_dt: string;
  end_dt: string;
  location_label?: string | null;
  formatted_address?: string | null;
  lat?: number | null;
  lng?: number | null;
  price_cents?: number;
  payout_amount_cents?: number | null;
  overrun_minutes?: number | null;
  overrun_amount_cents?: number | null;
  overrun_status?: string | null;
  reason?: string | null;
  check_in_at?: string | null;
  check_out_at?: string | null;
};
export type CalendarDay = {
  date: string;
  day: number;
  bookings: OperationsBooking[];
};
export type OperationsOverview = {
  pending_requests: OperationsBooking[];
  confirmed_bookings: OperationsBooking[];
  bookings_tomorrow: OperationsBooking[];
  upcoming_bookings: OperationsBooking[];
  bookings_in_progress: OperationsBooking[];
  past_bookings: OperationsBooking[];
  cancelled_bookings: OperationsBooking[];
  unsuccessful_bookings: OperationsBooking[];
  month_calendar: {
    year: number;
    month: number;
    month_label: string;
    days: CalendarDay[];
  };
};

export default function Bookings() {
  const router = useRouter();
  const [selected, setSelected] = useState<string[]>([]);
  const [nannyId, setNannyId] = useState<number | null>(null);
  const [locations, setLocations] = useState<Location[]>([]);
  const [locationId, setLocationId] = useState("");
  const [startTime, setStartTime] = useState("08:00");
  const [endTime, setEndTime] = useState("17:00");
  const [reason, setReason] = useState("");
  const [responsibilities, setResponsibilities] = useState("");
  const [kids, setKids] = useState("1");
  const [nanniesNeeded, setNanniesNeeded] = useState("1");
  const [adultPresent, setAdultPresent] = useState("parent");
  const [mealOption, setMealOption] = useState("meal_provided");
  const [foodRestrictions, setFoodRestrictions] = useState("");
  const [dogsInfo, setDogsInfo] = useState("");
  const [sleepover, setSleepover] = useState(false);
  const [sleepoverExpectations, setSleepoverExpectations] = useState("");
  const [sleepoverReason, setSleepoverReason] = useState("");
  const [accepted, setAccepted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState("");
  const [complete, setComplete] = useState<number | null>(null);
  const [parentView, setParentView] = useState<"plan" | "manage">("plan");
  const [estimate, setEstimate] = useState<BookingEstimate | null>(null);
  const [estimating, setEstimating] = useState(false);
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod | null>(null);
  const [paymentBusy, setPaymentBusy] = useState(false);
  useEffect(() => {
    apiJson<Location[]>("/parents/me/locations")
      .then((rows) => {
        setLocations(rows);
        const preferred = rows.find((row) => row.is_default) || rows[0];
        if (preferred) setLocationId(String(preferred.id));
      })
      .catch(() => undefined)
      .finally(() => {
        const id = Number(
          new URLSearchParams(window.location.search).get("nanny"),
        );
        if (Number.isFinite(id) && id > 0) setNannyId(id);
      });
    apiJson<PaymentMethod>("/parent/payment-method")
      .then(setPaymentMethod)
      .catch(() => undefined);
    const params = new URLSearchParams(window.location.search);
    const reference = params.get("reference") || params.get("trxref");
    if (params.get("payment_method") === "verify" && reference) {
      apiJson<PaymentMethod>("/parent/payment-method/verify", {
        method: "POST",
        body: JSON.stringify({ reference }),
      })
        .then((result) => {
          setPaymentMethod(result);
          setMessage("Payment authorised securely through Paystack. You can now send your booking request.");
          params.delete("payment_method");
          params.delete("reference");
          params.delete("trxref");
          window.history.replaceState({}, "", `${window.location.pathname}${params.toString() ? `?${params}` : ""}`);
        })
        .catch((error) => setMessage(error instanceof Error ? error.message : "Unable to verify card."));
    }
    const restoreTimer = window.setTimeout(() => {
      const saved = window.sessionStorage.getItem("my-nanny-booking-draft");
      if (!saved) return;
      try {
        const draft = JSON.parse(saved) as Record<string, unknown>;
        if (Array.isArray(draft.selected)) setSelected(draft.selected.filter((value): value is string => typeof value === "string"));
        if (typeof draft.locationId === "string") setLocationId(draft.locationId);
        if (typeof draft.startTime === "string") setStartTime(draft.startTime);
        if (typeof draft.endTime === "string") setEndTime(draft.endTime);
        if (typeof draft.reason === "string") setReason(draft.reason);
        if (typeof draft.responsibilities === "string") setResponsibilities(draft.responsibilities);
        if (typeof draft.kids === "string") setKids(draft.kids);
        if (typeof draft.nanniesNeeded === "string") setNanniesNeeded(draft.nanniesNeeded);
        if (typeof draft.adultPresent === "string") setAdultPresent(draft.adultPresent);
        if (typeof draft.mealOption === "string") setMealOption(draft.mealOption);
        if (typeof draft.foodRestrictions === "string") setFoodRestrictions(draft.foodRestrictions);
        if (typeof draft.dogsInfo === "string") setDogsInfo(draft.dogsInfo);
        if (typeof draft.sleepover === "boolean") setSleepover(draft.sleepover);
        if (typeof draft.sleepoverExpectations === "string") setSleepoverExpectations(draft.sleepoverExpectations);
        if (typeof draft.sleepoverReason === "string") setSleepoverReason(draft.sleepoverReason);
        if (typeof draft.accepted === "boolean") setAccepted(draft.accepted);
      } catch {
        window.sessionStorage.removeItem("my-nanny-booking-draft");
      }
    }, 0);
    return () => window.clearTimeout(restoreTimer);
  }, []);
  function toggle(date: string) {
    setSelected((current) =>
      current.includes(date)
        ? current.filter((item) => item !== date)
        : [...current, date].sort(),
    );
  }
  function slot(date: string, time: string) {
    return new Date(`${date}T${time}:00+02:00`).toISOString();
  }
  async function calculateEstimate() {
    if (!selected.length) {
      setMessage("Choose at least one date to calculate the price.");
      return;
    }
    setEstimating(true);
    setMessage("");
    try {
      const result = await apiJson<BookingEstimate>("/booking-requests/estimate", {
        method: "POST",
        body: JSON.stringify({
          slots: selected.map((date) => ({ starts_at: slot(date, startTime), ends_at: slot(date, endTime) })),
          sleepover,
          requested_nannies_count: Number(nanniesNeeded),
          kids_count: Number(kids),
        }),
      });
      setEstimate(result);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to calculate the booking price.");
    } finally {
      setEstimating(false);
    }
  }
  async function addPaymentMethod() {
    setPaymentBusy(true);
    setMessage("");
    try {
      const callback = new URL(window.location.href);
      callback.searchParams.set("payment_method", "verify");
      const result = await apiJson<{ authorization_url?: string }>("/parent/payment-method/initialize", {
        method: "POST",
        body: JSON.stringify({ callback_url: callback.toString() }),
      });
      if (!result.authorization_url) throw new Error("Paystack payment authorisation could not be started.");
      window.location.href = result.authorization_url;
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to start card setup.");
      setPaymentBusy(false);
    }
  }
  function viewAvailableNannies() {
    if (!selected.length) {
      setMessage("Choose at least one date before viewing available nannies.");
      return;
    }
    if (!locationId) {
      setMessage("Choose a booking address before viewing available nannies.");
      return;
    }
    const selectedLocation = locations.find((location) => String(location.id) === locationId);
    window.sessionStorage.setItem("my-nanny-booking-draft", JSON.stringify({
      selected, locationId, startTime, endTime, reason, responsibilities, kids, nanniesNeeded,
      adultPresent, mealOption, foodRestrictions, dogsInfo, sleepover,
      sleepoverExpectations, sleepoverReason, accepted,
      lat: selectedLocation?.lat,
      lng: selectedLocation?.lng,
      locationLabel: selectedLocation?.label || selectedLocation?.formatted_address || "Booking address",
      slots: selected.map((date) => ({ starts_at: slot(date, startTime), ends_at: slot(date, endTime) })),
    }));
    router.push("/caregivers?booking=1");
  }
  async function submit() {
    if (!nannyId) {
      setMessage("Choose a nanny before making a booking.");
      return;
    }
    if (!selected.length) {
      setMessage("Choose at least one date.");
      return;
    }
    if (!reason.trim() || !responsibilities.trim() || !accepted) {
      setMessage("Complete the care details and confirm the booking rules.");
      return;
    }
    if (sleepover && (!sleepoverExpectations.trim() || !sleepoverReason.trim())) {
      setMessage("Complete the sleepover expectations and reason before sending the request.");
      return;
    }
    setSubmitting(true);
    setMessage("");
    try {
      const result = await apiJson<BookingResponse>("/booking-requests", {
        method: "POST",
        body: JSON.stringify({
          nanny_id: nannyId,
          slots: selected.map((date) => ({
            starts_at: slot(date, startTime),
            ends_at: slot(date, endTime),
          })),
          location_id: locationId ? Number(locationId) : null,
          kids_count: Number(kids),
          responsibilities,
          adult_present: adultPresent,
          booking_reason: reason,
          meal_option: mealOption,
          food_restrictions: foodRestrictions,
          dogs_info: dogsInfo,
          sleepover,
          sleepover_expectations: sleepover ? sleepoverExpectations : null,
          sleepover_reason: sleepover ? sleepoverReason : null,
          disclaimer_basic_upkeep: true,
          disclaimer_medicine: true,
          disclaimer_extra_hours: true,
          disclaimer_transport: true,
        }),
      });
      if (result.requires_payment_method) {
        setMessage(
          result.message || "Add a payment method before sending this request.",
        );
      } else if (result.booking_request_id) {
        window.sessionStorage.removeItem("my-nanny-booking-draft");
        setComplete(result.booking_request_id);
      }
    } catch (err) {
      setMessage(
        err instanceof Error
          ? err.message
          : "Unable to create booking request.",
      );
    } finally {
      setSubmitting(false);
    }
  }
  return (
    <AuthenticatedPage>
      {(role) =>
        role === "parent" ? (
          <div className="mx-auto max-w-6xl">
            <div className="mb-7 flex w-fit rounded-full bg-slate-100 p-1">
              <button className={`rounded-full px-5 py-2 text-sm font-bold ${parentView === "plan" ? "bg-white shadow-sm" : "text-[var(--muted)]"}`} onClick={() => setParentView("plan")}>Plan care</button>
              <button className={`rounded-full px-5 py-2 text-sm font-bold ${parentView === "manage" ? "bg-white shadow-sm" : "text-[var(--muted)]"}`} onClick={() => setParentView("manage")}>Manage bookings</button>
            </div>
            {parentView === "manage" ? (
              <ParentBookingManager />
            ) : (
              <>
            <div className="eyebrow">Plan care</div>
            <h1 className="display mt-2 text-4xl sm:text-5xl">
              Choose your dates.
            </h1>
            <p className="mt-3 text-[var(--muted)]">
              Select one or more days and tell the nanny what your family needs.
            </p>
            {complete ? (
              <div className="card mt-8 p-10 text-center">
                <CheckCircle2
                  className="mx-auto text-[var(--green)]"
                  size={48}
                />
                <h2 className="mt-4 text-2xl font-bold">Request sent</h2>
                <p className="mt-2 text-[var(--muted)]">
                  Booking request #{complete} is waiting for the nanny’s
                  response.
                </p>
                <div className="mt-6 flex flex-wrap justify-center gap-3">
                  <button className="btn-primary" onClick={() => setParentView("manage")}>
                    Track this booking
                  </button>
                  <Link href="/dashboard" className="btn-secondary">
                    Back to home
                  </Link>
                </div>
              </div>
            ) : (
              <div className="mt-7 grid gap-6 xl:grid-cols-[1.15fr_.85fr]">
                <div className="card p-4 sm:p-6">
                  <MonthCalendar selectable selectedDates={selected} onSelect={toggle} />
                  <div className="mt-5 grid gap-4 sm:grid-cols-2">
                    <label>
                      <span className="mb-2 flex items-center gap-2 text-sm font-bold">
                        <Clock size={15} />
                        Arrival
                      </span>
                      <input
                        type="time"
                        className="field"
                        value={startTime}
                        onInput={(e) => setStartTime(e.currentTarget.value)}
                      />
                    </label>
                    <label>
                      <span className="mb-2 flex items-center gap-2 text-sm font-bold">
                        <Clock size={15} />
                        Finish
                      </span>
                      <input
                        type="time"
                        className="field"
                        value={endTime}
                        onInput={(e) => setEndTime(e.currentTarget.value)}
                      />
                    </label>
                  </div>
                </div>
                <aside className="card p-6">
                  <div className="flex items-center gap-3">
                    <CalendarDays className="text-[var(--blue-dark)]" />
                    <h2 className="text-xl font-bold">Booking details</h2>
                  </div>
                  <div className="mt-5 text-sm font-bold">
                    {selected.length
                      ? `${selected.length} date${selected.length === 1 ? "" : "s"} selected`
                      : "No dates selected yet"}
                  </div>
                  <div className="mt-4 rounded-2xl border border-[var(--line)] p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div><div className="text-sm font-bold">Secure payment</div><div className="mt-1 text-xs text-[var(--muted)]">{paymentMethod?.has_card ? `Payment securely authorised through Paystack${paymentMethod.card_brand && paymentMethod.card_last4 ? ` · ${paymentMethod.card_brand} ending ${paymentMethod.card_last4}` : ""}. My Nanny does not store your card details.` : "You will not be able to request a booking until Paystack authorisation has been completed. Card details are securely handled by Paystack and are not stored by My Nanny."}</div></div>
                      {paymentMethod?.has_card ? <CheckCircle2 className="text-[var(--green)]" size={22} /> : <button className="btn-secondary !min-h-9 shrink-0" disabled={paymentBusy} onClick={() => void addPaymentMethod()}>{paymentBusy ? "Opening Paystack..." : "Continue with Paystack"}</button>}
                    </div>
                  </div>
                  <div className="mt-5 grid gap-4">
                    <label>
                      <span className="mb-2 flex items-center gap-2 text-sm font-bold">
                        <MapPin size={15} />
                        Booking address
                      </span>
                      <select
                        className="field"
                        value={locationId}
                        onChange={(e) => setLocationId(e.target.value)}
                      >
                        <option value="">Choose an address</option>
                        {locations.map((location) => (
                          <option key={location.id} value={location.id}>
                            {location.label ||
                              location.formatted_address ||
                              `Address ${location.id}`}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      <span className="mb-2 block text-sm font-bold">
                        Number of nannies needed
                      </span>
                      <select
                        className="field"
                        value={nanniesNeeded}
                        onChange={(e) => {
                          setNanniesNeeded(e.target.value);
                          setEstimate(null);
                        }}
                      >
                        {[1, 2, 3, 4, 5].map((value) => (
                          <option key={value} value={value}>{value}</option>
                        ))}
                      </select>
                      <span className="mt-2 block text-xs text-[var(--muted)]">
                        The request stays open until every position is filled.
                      </span>
                    </label>
                    <label>
                      <span className="mb-2 block text-sm font-bold">
                        Number of children
                      </span>
                      <select
                        className="field"
                        value={kids}
                        onChange={(e) => setKids(e.target.value)}
                      >
                        {[1, 2, 3, 4, 5].map((value) => (
                          <option key={value}>{value}</option>
                        ))}
                      </select>
                    </label>
                    <label>
                      <span className="mb-2 block text-sm font-bold">
                        Reason for care
                      </span>
                      <textarea
                        className="field min-h-20"
                        value={reason}
                        onChange={(e) => setReason(e.target.value)}
                        placeholder="For example: date night or work commitment"
                      />
                    </label>
                    <label>
                      <span className="mb-2 block text-sm font-bold">Adult present at the address</span>
                      <select className="field" value={adultPresent} onChange={(e) => setAdultPresent(e.target.value)}>
                        <option value="parent">Parent present</option>
                        <option value="other_adult">Another adult present</option>
                        <option value="none">No adult present</option>
                      </select>
                    </label>
                    <label>
                      <span className="mb-2 block text-sm font-bold">Meal arrangement</span>
                      <select className="field" value={mealOption} onChange={(e) => setMealOption(e.target.value)}>
                        <option value="meal_provided">We provide a meal</option>
                        <option value="basics_provided">We provide kitchen basics</option>
                        <option value="own_meal">Nanny brings her own meal</option>
                      </select>
                    </label>
                    <label>
                      <span className="mb-2 block text-sm font-bold">Food restrictions</span>
                      <input className="field" value={foodRestrictions} onChange={(e) => setFoodRestrictions(e.target.value)} placeholder="Allergies or foods not allowed in the home" />
                    </label>
                    <label>
                      <span className="mb-2 block text-sm font-bold">Dogs at the property</span>
                      <input className="field" value={dogsInfo} onChange={(e) => setDogsInfo(e.target.value)} placeholder="Number, breed and access arrangements" />
                    </label>
                    <label className="flex items-start gap-3 rounded-xl border border-[var(--line)] p-3 text-sm">
                      <input type="checkbox" className="mt-1" checked={sleepover} onChange={(e) => setSleepover(e.target.checked)} />
                      <span><b>Sleepover booking</b><br /><span className="text-[var(--muted)]">The nanny will stay overnight.</span></span>
                    </label>
                    {sleepover && (
                      <div className="grid gap-4 rounded-2xl bg-amber-50 p-4">
                        <label><span className="mb-2 block text-sm font-bold">Sleepover expectations</span><textarea className="field min-h-20" value={sleepoverExpectations} onChange={(e) => setSleepoverExpectations(e.target.value)} placeholder="For example: The nanny needs to get up during the night if the children wake up." /></label>
                        <label><span className="mb-2 block text-sm font-bold">Reason for sleepover</span><textarea className="field min-h-20" value={sleepoverReason} onChange={(e) => setSleepoverReason(e.target.value)} placeholder="For example: We have a new baby in the house and need a break." /></label>
                      </div>
                    )}
                    <label>
                      <span className="mb-2 block text-sm font-bold">
                        What should the nanny help with?
                      </span>
                      <textarea
                        className="field min-h-24"
                        value={responsibilities}
                        onChange={(e) => setResponsibilities(e.target.value)}
                        placeholder="Childcare responsibilities and routine"
                      />
                    </label>
                    <label className="flex items-start gap-3 rounded-xl border border-[var(--line)] p-3 text-sm">
                      <input
                        type="checkbox"
                        className="mt-1"
                        checked={accepted}
                        onChange={(e) => setAccepted(e.target.checked)}
                      />
                      <span>
                        I understand the care, medicine, additional-hours and
                        safe-transport rules for this booking.
                      </span>
                    </label>
                  </div>
                  {message && (
                    <div
                      role="alert"
                      className="mt-4 rounded-xl bg-amber-50 p-3 text-sm text-amber-900"
                    >
                      {message}
                    </div>
                  )}
                  <div className="mt-5 rounded-2xl bg-slate-50 p-4">
                    {estimate ? (
                      <div className="grid gap-2 text-sm">
                        <div className="flex justify-between"><span>Nanny wage</span><b>R{(estimate.per_nanny_wage_cents / 100).toFixed(2)}</b></div>
                        <div className="flex justify-between"><span>Booking fee ({(estimate.booking_fee_pct * 100).toFixed(0)}%)</span><b>R{(estimate.per_nanny_fee_cents / 100).toFixed(2)}</b></div>
                        <div className="flex justify-between"><span>Per nanny</span><b>R{(estimate.per_nanny_total_cents / 100).toFixed(2)}</b></div>
                        <div className="flex justify-between border-t border-[var(--line)] pt-2 text-base"><span>Estimated total for {nanniesNeeded}</span><b>R{(estimate.selected_total_cents / 100).toFixed(2)}</b></div>
                      </div>
                    ) : <p className="text-sm text-[var(--muted)]">Calculate the price before sending your request.</p>}
                    <button className="btn-secondary mt-3 w-full" disabled={estimating || !selected.length} onClick={() => void calculateEstimate()}>{estimating ? <LoaderCircle className="animate-spin" size={17} /> : <Wallet size={17} />}{estimating ? "Calculating..." : estimate ? "Recalculate price" : "Calculate price"}</button>
                  </div>
                  <button
                    className="btn-primary mt-6 w-full"
                    disabled={submitting || (Boolean(nannyId) && !paymentMethod?.has_card)}
                    onClick={() => nannyId ? void submit() : viewAvailableNannies()}
                  >
                    {submitting ? (
                      <>
                        <LoaderCircle className="animate-spin" size={17} />
                        Sending...
                      </>
                    ) : (
                      nannyId ? "Send booking request" : "View available nannies"
                    )}
                  </button>
                </aside>
              </div>
            )}
              </>
            )}
          </div>
        ) : (
          <OperationsCalendar role={role} />
        )
      }
    </AuthenticatedPage>
  );
}

function OperationsCalendar({ role }: { role: string }) {
  const [overview, setOverview] = useState<OperationsOverview | null>(null);
  const [selectedDay, setSelectedDay] = useState<CalendarDay | null>(null);
  const [selectedBookingId, setSelectedBookingId] = useState<number | null>(
    null,
  );
  const [loading, setLoading] = useState(role === "admin");
  const [error, setError] = useState("");
  useEffect(() => {
    if (role !== "admin") return;
    apiJson<OperationsOverview>("/admin/bookings/overview")
      .then((data) => {
        setOverview(data);
        const requested = Number(
          new URLSearchParams(window.location.search).get("booking"),
        );
        if (!Number.isFinite(requested) || requested <= 0) return;
        const day = data.month_calendar.days.find((item) =>
          item.bookings.some(
            (booking) =>
              booking.booking_id === requested ||
              booking.request_id === requested,
          ),
        );
        if (day) {
          setSelectedDay(day);
          setSelectedBookingId(requested);
        }
      })
      .catch((err) =>
        setError(
          err instanceof Error ? err.message : "Unable to load bookings.",
        ),
      )
      .finally(() => setLoading(false));
  }, [role]);
  if (role === "nanny") return <NannyDutyBookings />;
  if (role !== "admin")
    return (
      <div className="mx-auto max-w-6xl">
        <div className="eyebrow">Your schedule</div>
        <h1 className="display mt-2 text-4xl sm:text-5xl">
          Bookings calendar.
        </h1>
        <div className="card mt-7 p-8 text-center">
          <p className="text-[var(--muted)]">
            Accepted bookings appear in your requests and dashboard.
          </p>
          <Link href="/requests" className="btn-primary mt-5">
            View booking requests
          </Link>
        </div>
      </div>
    );
  const days = overview?.month_calendar.days || [];
  const events = days
    .filter((day) => day.bookings.length)
    .map((day) => ({
      date: day.date,
      label: `${day.bookings.length} booking${day.bookings.length === 1 ? "" : "s"}`,
      tone: day.bookings.some(
        (booking) => booking.booking_state === "in_progress",
      )
        ? ("green" as const)
        : ("blue" as const),
    }));
  function openDay(date: string) {
    setSelectedDay(
      days.find((day) => day.date === date) || {
        date,
        day: Number(date.slice(-2)),
        bookings: [],
      },
    );
  }
  return (
    <div className="mx-auto max-w-6xl">
      <div className="eyebrow">Booking operations</div>
      <h1 className="display mt-2 text-4xl sm:text-5xl">Bookings calendar.</h1>
      <p className="mt-3 text-[var(--muted)]">
        Select any date to review its bookings and operational status.
      </p>
      {error && (
        <div className="mt-5 rounded-xl bg-amber-50 p-4 text-sm text-amber-900">
          {error}
        </div>
      )}
      <div className="card mt-7 p-5">
        {loading ? (
          <div className="flex min-h-[500px] items-center justify-center">
            <LoaderCircle className="animate-spin" />
          </div>
        ) : (
          <MonthCalendar events={events} onSelect={openDay} />
        )}
      </div>
      {selectedDay && (
        <DayBookingsDrawer
          day={selectedDay}
          initialBookingId={selectedBookingId}
          onClose={() => {
            setSelectedDay(null);
            setSelectedBookingId(null);
          }}
        />
      )}
    </div>
  );
}

export function DayBookingsDrawer({
  day,
  initialBookingId,
  onClose,
}: {
  day: CalendarDay;
  initialBookingId?: number | null;
  onClose: () => void;
}) {
  const [selectedBooking, setSelectedBooking] =
    useState<OperationsBooking | null>(() =>
      initialBookingId
        ? day.bookings.find(
            (booking) =>
              booking.booking_id === initialBookingId ||
              booking.request_id === initialBookingId,
          ) || null
        : null,
    );
  const label = new Date(`${day.date}T12:00:00`).toLocaleDateString("en-ZA", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
  return (
    <div
      className="fixed inset-0 z-50 bg-[var(--ink)]/35 backdrop-blur-sm"
      onMouseDown={onClose}
    >
      <aside
        className="ml-auto h-full w-full max-w-2xl overflow-auto bg-white shadow-2xl"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="sticky top-0 z-10 border-b border-[var(--line)] bg-white/95 p-6 backdrop-blur">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-3">
              {selectedBooking && (
                <button
                  className="btn-quiet !min-h-10 !px-3"
                  onClick={() => setSelectedBooking(null)}
                  aria-label="Back to daily bookings"
                >
                  <ArrowLeft />
                </button>
              )}
              <div>
                <div className="eyebrow">
                  {selectedBooking ? "Booking details" : "Daily operations"}
                </div>
                <h2 className="mt-2 text-2xl font-bold">
                  {selectedBooking
                    ? `Booking #${selectedBooking.booking_id || selectedBooking.request_id}`
                    : label}
                </h2>
                <p className="mt-1 text-sm text-[var(--muted)]">
                  {selectedBooking ? (
                    label
                  ) : (
                    <>
                      {day.bookings.length} booking
                      {day.bookings.length === 1 ? "" : "s"}
                    </>
                  )}
                </p>
              </div>
            </div>
            <button
              className="btn-quiet !min-h-10 !px-3"
              onClick={onClose}
              aria-label="Close day bookings"
            >
              <X />
            </button>
          </div>
        </header>
        <div className="grid gap-4 p-6">
          {selectedBooking ? (
            <BookingDetail booking={selectedBooking} />
          ) : day.bookings.length ? (
            day.bookings.map((booking, index) => (
              <BookingCard
                key={`${booking.booking_id || booking.request_id}-${index}`}
                booking={booking}
                onOpen={() => setSelectedBooking(booking)}
              />
            ))
          ) : (
            <div className="rounded-3xl bg-slate-50 p-10 text-center">
              <CalendarDays className="mx-auto text-slate-400" size={32} />
              <h3 className="mt-4 text-lg font-bold">
                No bookings on this date
              </h3>
              <p className="mt-2 text-sm text-[var(--muted)]">
                Choose another highlighted date to review its schedule.
              </p>
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}

function BookingCard({
  booking,
  onOpen,
}: {
  booking: OperationsBooking;
  onOpen: () => void;
}) {
  const start = new Date(booking.start_dt);
  const end = new Date(booking.end_dt);
  return (
    <button
      onClick={onOpen}
      className="group w-full rounded-3xl border border-[var(--line)] p-5 text-left transition hover:-translate-y-0.5 hover:border-[var(--blue)] hover:shadow-lg focus-visible:ring-2 focus-visible:ring-[var(--blue)]"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-2xl font-bold">
            {start.toLocaleTimeString("en-ZA", {
              hour: "2-digit",
              minute: "2-digit",
            })}{" "}
            -{" "}
            {end.toLocaleTimeString("en-ZA", {
              hour: "2-digit",
              minute: "2-digit",
            })}
          </div>
          <div className="mt-1 text-sm text-[var(--muted)]">
            Booking #{booking.booking_id || booking.request_id}
          </div>
        </div>
        <span className="pill capitalize">
          {(booking.booking_state || booking.status || "scheduled").replaceAll(
            "_",
            " ",
          )}
        </span>
      </div>
      <div className="mt-5 grid gap-3 rounded-2xl bg-slate-50 p-4 text-sm">
        <div className="flex items-center gap-3">
          <UserRound size={17} />
          <b>{booking.nanny_name}</b>
          <span className="text-[var(--muted)]">
            with {booking.parent_name}
          </span>
        </div>
        <div className="flex items-start gap-3">
          <MapPin className="mt-0.5 shrink-0" size={17} />
          <span>{booking.location_label || "Location not recorded"}</span>
        </div>
        {booking.check_in_at && (
          <div className="flex items-center gap-3">
            <CheckCircle2 size={17} />
            <span>
              Checked in{" "}
              {new Date(booking.check_in_at).toLocaleTimeString("en-ZA", {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </span>
          </div>
        )}
      </div>
      <div className="mt-4 flex items-center justify-end gap-2 text-sm font-bold text-[var(--blue-dark)]">
        View full job <ArrowUpRight size={16} />
      </div>
    </button>
  );
}

function BookingDetail({ booking }: { booking: OperationsBooking }) {
  const [mapOpen, setMapOpen] = useState(false);
  const start = new Date(booking.start_dt);
  const end = new Date(booking.end_dt);
  const durationHours = Math.max(
    (end.getTime() - start.getTime()) / 3_600_000,
    0,
  );
  const total = (booking.price_cents || 0) / 100;
  const hourly = durationHours ? total / durationHours : 0;
  const status = (
    booking.booking_state ||
    booking.status ||
    "scheduled"
  ).replaceAll("_", " ");
  const mapUrl =
    booking.lat != null && booking.lng != null
      ? `https://www.google.com/maps/search/?api=1&query=${booking.lat},${booking.lng}`
      : booking.formatted_address
        ? `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(booking.formatted_address)}`
        : null;
  const mapQuery =
    booking.lat != null && booking.lng != null
      ? `${booking.lat},${booking.lng}`
      : booking.formatted_address || booking.location_label || "";
  const mapEmbedUrl = `https://maps.google.com/maps?q=${encodeURIComponent(mapQuery)}&z=15&output=embed`;
  return (
    <div className="grid gap-5">
      <section className="rounded-3xl bg-[var(--blue-dark)] p-6 text-white">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="text-sm font-bold text-white/60">
              {start.toLocaleDateString("en-ZA", {
                weekday: "long",
                day: "numeric",
                month: "long",
              })}
            </div>
            <div className="mt-2 text-3xl font-bold">
              {start.toLocaleTimeString("en-ZA", {
                hour: "2-digit",
                minute: "2-digit",
              })}{" "}
              -{" "}
              {end.toLocaleTimeString("en-ZA", {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </div>
            <div className="mt-2 text-sm text-white/70">
              {durationHours.toFixed(durationHours % 1 ? 1 : 0)} hours
            </div>
          </div>
          <span className="rounded-full bg-white/15 px-4 py-2 text-sm font-bold capitalize">
            {status}
          </span>
        </div>
      </section>
      <section className="rounded-3xl border border-[var(--line)] p-5">
        <h3 className="text-lg font-bold">People</h3>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <DetailItem label="Nanny" value={booking.nanny_name} />
          <DetailItem label="Parent" value={booking.parent_name} />
          <DetailItem label="Parent email" value={booking.parent_email} />
          <DetailItem label="Parent telephone" value={booking.parent_phone} />
          <DetailItem
            label="Booking reference"
            value={`#${booking.booking_id || booking.request_id}`}
          />
        </div>
        {booking.parent_phone && (
          <div className="mt-5 flex flex-wrap gap-3 border-t border-[var(--line)] pt-5">
            <a className="btn-secondary" href={`tel:${booking.parent_phone}`}>
              <Phone size={16} />
              Call parent
            </a>
            <a
              className="btn-primary !bg-[#168c4b]"
              href={`https://wa.me/${whatsappNumber(booking.parent_phone)}`}
              target="_blank"
              rel="noreferrer"
            >
              <MessageCircle size={16} />
              Open WhatsApp
            </a>
            {booking.parent_user_id && (
              <Link
                className="btn-secondary"
                href={`/communicator?user=${booking.parent_user_id}&channel=${booking.parent_preferred_channel || "whatsapp"}`}
              >
                <MessageCircle size={16} />
                Open in Communicator
              </Link>
            )}
          </div>
        )}
      </section>
      <button
        type="button"
        disabled={!mapUrl}
        onClick={() => setMapOpen(true)}
        className="group w-full rounded-3xl border border-[var(--line)] p-5 text-left transition hover:border-[var(--blue)] hover:shadow-md disabled:cursor-default disabled:hover:border-[var(--line)] disabled:hover:shadow-none"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="text-lg font-bold">Location</h3>
            <p className="mt-3 text-sm leading-6 text-[var(--muted)]">
              {booking.formatted_address ||
                booking.location_label ||
                "Location not recorded"}
            </p>
            {booking.lat != null && booking.lng != null && (
              <p className="mt-2 text-xs text-slate-400">
                {booking.lat.toFixed(5)}, {booking.lng.toFixed(5)}
              </p>
            )}
          </div>
          <MapPin className="shrink-0 text-[var(--coral)] transition group-hover:scale-110" />
        </div>
        {mapUrl && (
          <div className="mt-4 flex items-center gap-2 text-sm font-bold text-[var(--blue-dark)]">
            View map <ArrowUpRight size={16} />
          </div>
        )}
      </button>
      {mapOpen && (
        <MapPreview
          address={
            booking.formatted_address ||
            booking.location_label ||
            "Booking location"
          }
          embedUrl={mapEmbedUrl}
          mapsUrl={mapUrl!}
          onClose={() => setMapOpen(false)}
        />
      )}
      <section className="rounded-3xl border border-[var(--line)] p-5">
        <div className="flex items-center gap-3">
          <Wallet className="text-[var(--green)]" />
          <h3 className="text-lg font-bold">Rates & payment</h3>
        </div>
        <div className="mt-5 grid grid-cols-2 gap-3">
          <MoneyMetric label="Booking total" value={total} />
          <MoneyMetric label="Effective hourly" value={hourly} />
          {booking.payout_amount_cents != null && (
            <MoneyMetric
              label="Nanny payout"
              value={booking.payout_amount_cents / 100}
            />
          )}{" "}
          {booking.overrun_amount_cents != null && (
            <MoneyMetric
              label="Overtime amount"
              value={booking.overrun_amount_cents / 100}
            />
          )}
        </div>
        {booking.overrun_minutes != null && (
          <p className="mt-4 text-sm text-[var(--muted)]">
            Overtime: {booking.overrun_minutes} minutes
            {booking.overrun_status
              ? ` · ${booking.overrun_status.replaceAll("_", " ")}`
              : ""}
          </p>
        )}
      </section>
      <section className="rounded-3xl border border-[var(--line)] p-5">
        <h3 className="text-lg font-bold">Duty activity</h3>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <DetailItem
            label="Check-in"
            value={
              booking.check_in_at
                ? new Date(booking.check_in_at).toLocaleString("en-ZA", {
                    dateStyle: "medium",
                    timeStyle: "short",
                  })
                : "Not checked in"
            }
          />
          <DetailItem
            label="Check-out"
            value={
              booking.check_out_at
                ? new Date(booking.check_out_at).toLocaleString("en-ZA", {
                    dateStyle: "medium",
                    timeStyle: "short",
                  })
                : "Not checked out"
            }
          />
        </div>
      </section>
      <AdminBookingActions booking={booking} />
    </div>
  );
}

type AvailableNanny = {
  nanny_id: number;
  name?: string;
  distance_km?: number | null;
  location_hint?: string | null;
  average_rating_12m?: number | null;
};

function AdminBookingActions({ booking }: { booking: OperationsBooking }) {
  const requestId = booking.request_id;
  const bookingId = booking.booking_id;
  const [available, setAvailable] = useState<AvailableNanny[]>([]);
  const [nannyId, setNannyId] = useState("");
  const [loadingNannies, setLoadingNannies] = useState(false);
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  const state = booking.booking_state || booking.status || "";
  const closed = ["cancelled", "completed", "past", "rejected"].includes(state);

  async function runAction(key: string, path: string, body?: unknown) {
    setBusy(key);
    setMessage("");
    try {
      await apiJson(path, {
        method: "POST",
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      setMessage("Booking updated. Refreshing the operations view...");
      window.setTimeout(() => window.location.reload(), 800);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to update booking.");
      setBusy("");
    }
  }

  function reasonAction(key: string, path: string, promptText: string) {
    const reason = window.prompt(promptText);
    if (!reason?.trim()) return;
    void runAction(key, path, { reason: reason.trim() });
  }

  async function findAvailableNannies() {
    if (!requestId) return;
    setLoadingNannies(true);
    setMessage("");
    try {
      const result = await apiJson<{ results?: AvailableNanny[] } | AvailableNanny[]>(
        `/admin/booking-requests/${requestId}/available-nannies`,
      );
      const rows = Array.isArray(result) ? result : result.results || [];
      setAvailable(rows);
      if (rows[0]) setNannyId(String(rows[0].nanny_id));
      if (!rows.length) setMessage("No approved nannies are available for every requested time slot within 30 km.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to find available nannies.");
    } finally {
      setLoadingNannies(false);
    }
  }

  function assignNanny() {
    if (!requestId || !nannyId) return;
    const reason = window.prompt("Why are you manually assigning this nanny?");
    if (!reason?.trim()) return;
    void runAction("assign", `/admin/booking-requests/${requestId}/assign-nanny`, {
      assign_nanny_id: Number(nannyId),
      reason: reason.trim(),
    });
  }

  return (
    <section className="rounded-3xl border border-[var(--line)] p-5">
      <div className="flex items-center gap-3">
        <ShieldAlert className="text-[var(--blue-dark)]" />
        <div>
          <h3 className="text-lg font-bold">Admin controls</h3>
          <p className="mt-1 text-sm text-[var(--muted)]">Actions here update the booking, notifications and operational audit trail.</p>
        </div>
      </div>
      {message && <div className="mt-4 rounded-xl bg-[var(--blue-pale)] p-3 text-sm">{message}</div>}
      {!closed && requestId && (
        <div className="mt-5 grid gap-3">
          <div className="flex flex-wrap gap-3">
            {["pending_admin", "tbc"].includes(booking.status || "") && (
              <button className="btn-primary" disabled={Boolean(busy)} onClick={() => void runAction("approve", `/admin/booking-requests/${requestId}/approve`)}><CheckCircle2 size={17} />Approve request</button>
            )}
            <button className="btn-secondary" disabled={loadingNannies || Boolean(busy)} onClick={() => void findAvailableNannies()}><UserRoundPlus size={17} />{loadingNannies ? "Finding..." : "Reassign nanny"}</button>
            {["pending_admin", "tbc"].includes(booking.status || "") && (
              <button className="btn-quiet text-red-700" disabled={Boolean(busy)} onClick={() => reasonAction("reject", `/admin/booking-requests/${requestId}/reject`, "Why is this booking request being rejected?")}><X size={16} />Reject request</button>
            )}
            <button className="btn-quiet text-red-700" disabled={Boolean(busy)} onClick={() => reasonAction("cancel", `/admin/booking-requests/${requestId}/cancel`, "Why is this booking being cancelled by admin?")}><X size={16} />Cancel booking</button>
          </div>
          {available.length > 0 && (
            <div className="rounded-2xl bg-slate-50 p-4">
              <label className="text-sm font-bold" htmlFor={`available-nanny-${requestId}`}>Available nanny</label>
              <div className="mt-2 flex flex-col gap-3 sm:flex-row">
                <select id={`available-nanny-${requestId}`} className="field" value={nannyId} onChange={(event) => setNannyId(event.target.value)}>
                  {available.map((nanny) => <option key={nanny.nanny_id} value={nanny.nanny_id}>{nanny.name || `Nanny #${nanny.nanny_id}`}{nanny.distance_km != null ? ` · ${nanny.distance_km.toFixed(1)} km` : ""}{nanny.average_rating_12m != null ? ` · ${nanny.average_rating_12m.toFixed(1)} stars` : ""}</option>)}
                </select>
                <button className="btn-primary shrink-0" disabled={!nannyId || Boolean(busy)} onClick={assignNanny}>Confirm assignment</button>
              </div>
            </div>
          )}
        </div>
      )}
      {!closed && bookingId && (
        <div className="mt-5 flex flex-wrap gap-3 border-t border-[var(--line)] pt-5">
          <button className="btn-secondary" disabled={Boolean(busy)} onClick={() => reasonAction("nanny-no-show", `/admin/bookings/${bookingId}/mark-no-show`, "Why are you marking the nanny as a no-show?")}>Mark nanny no-show</button>
          <button className="btn-secondary" disabled={Boolean(busy) || !booking.check_in_at} title={!booking.check_in_at ? "The nanny must check in first" : undefined} onClick={() => reasonAction("parent-no-show", `/admin/bookings/${bookingId}/mark-parent-no-show`, "Why are you marking the parent as a no-show?")}>Mark parent no-show</button>
        </div>
      )}
      {closed && <p className="mt-4 text-sm text-[var(--muted)]">This booking is closed. Operational actions are no longer available.</p>}
    </section>
  );
}

function DetailItem({
  label,
  value,
}: {
  label: string;
  value?: string | null;
}) {
  return (
    <div>
      <div className="text-xs font-bold uppercase tracking-wider text-[var(--muted)]">
        {label}
      </div>
      <div className="mt-1 break-words text-sm font-semibold">
        {value || "Not recorded"}
      </div>
    </div>
  );
}

function MapPreview({
  address,
  embedUrl,
  mapsUrl,
  onClose,
}: {
  address: string;
  embedUrl: string;
  mapsUrl: string;
  onClose: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-[var(--ink)]/45 p-4 backdrop-blur-sm"
      onMouseDown={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`Map for ${address}`}
        className="w-full max-w-2xl overflow-hidden rounded-[28px] bg-white shadow-2xl"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="flex items-start justify-between gap-4 border-b border-[var(--line)] p-5">
          <div>
            <div className="eyebrow">Booking location</div>
            <h3 className="mt-2 text-xl font-bold">{address}</h3>
          </div>
          <button
            className="btn-quiet !min-h-10 !px-3"
            onClick={onClose}
            aria-label="Close map"
          >
            <X />
          </button>
        </header>
        <div className="aspect-[4/3] max-h-[520px] bg-slate-100 sm:aspect-[16/9]">
          <iframe
            src={embedUrl}
            title={`Map showing ${address}`}
            loading="lazy"
            referrerPolicy="no-referrer-when-downgrade"
            className="h-full w-full border-0"
            allowFullScreen
          />
        </div>
        <footer className="flex flex-wrap items-center justify-between gap-3 p-4">
          <p className="text-xs text-[var(--muted)]">
            Location shown from the booking coordinates.
          </p>
          <a
            href={mapsUrl}
            target="_blank"
            rel="noreferrer"
            className="btn-primary"
          >
            Open full map <ArrowUpRight size={16} />
          </a>
        </footer>
      </div>
    </div>
  );
}

function MoneyMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-2xl bg-slate-50 p-4">
      <div className="text-xs font-bold uppercase tracking-wider text-[var(--muted)]">
        {label}
      </div>
      <div className="mt-2 text-xl font-bold">
        R
        {value.toLocaleString("en-ZA", {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        })}
      </div>
    </div>
  );
}

function whatsappNumber(phone: string) {
  const digits = phone.replace(/\D/g, "");
  return digits.startsWith("0") ? `27${digits.slice(1)}` : digits;
}
