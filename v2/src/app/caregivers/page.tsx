"use client";

import { AuthenticatedPage } from "@/components/authenticated-page";
import { apiJson } from "@/lib/api";
import { BadgeCheck, CalendarDays, Check, Clock, Heart, LoaderCircle, MapPin, Pencil, PlayCircle, Radio, Search, Star } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";

export type NannyResult = {
  nanny_id: number; name: string; profile_photo_url?: string | null;
  distance_km?: number | null; average_rating_12m?: number | null;
  review_count_12m?: number; completed_jobs_count?: number;
  location_hint?: string | null; profile_summary?: string | null;
  qualifications?: { id: number; name: string }[]; tags?: { id: number; name: string }[];
  trust_badges?: { key: string; label: string }[];
};
type SearchResponse = { results: NannyResult[]; message?: string | null };
type BookingDraft = {
  slots?: { starts_at: string; ends_at: string }[];
  lat?: number;
  lng?: number;
  locationLabel?: string;
  locationId?: string;
  reason?: string;
  responsibilities?: string;
  kids?: string;
  nanniesNeeded?: string;
  adultPresent?: string;
  mealOption?: string;
  foodRestrictions?: string;
  dogsInfo?: string;
  sleepover?: boolean;
  sleepoverExpectations?: string;
  sleepoverReason?: string;
  accepted?: boolean;
};

function readBookingDraft() {
  if (new URLSearchParams(window.location.search).get("booking") !== "1") return null;
  const saved = window.sessionStorage.getItem("my-nanny-booking-draft");
  if (!saved) return null;
  try {
    return JSON.parse(saved) as BookingDraft;
  } catch {
    window.sessionStorage.removeItem("my-nanny-booking-draft");
    return null;
  }
}

function bookingAwareSearch(maxDistanceKm: number) {
  const parsed = readBookingDraft();
  if (parsed?.slots?.length) {
    return apiJson<SearchResponse>("/nannies/search-by-time", {
      method: "POST",
      body: JSON.stringify({ slots: parsed.slots, lat: parsed.lat, lng: parsed.lng, max_distance_km: maxDistanceKm }),
    });
  }
  return apiJson<SearchResponse>("/nannies/search", { method: "POST", body: JSON.stringify({ max_distance_km: maxDistanceKm }) });
}

export default function Caregivers() {
  const [results, setResults] = useState<NannyResult[]>([]);
  const [favourites, setFavourites] = useState<number[]>([]);
  const [query, setQuery] = useState("");
  const [distance, setDistance] = useState("10");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [bookingDraft, setBookingDraft] = useState<BookingDraft | null>(null);
  const [broadcastEnabled, setBroadcastEnabled] = useState(false);
  const [selectedNannies, setSelectedNannies] = useState<number[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [broadcastMessage, setBroadcastMessage] = useState("");

  async function load() {
    setLoading(true); setError("");
    try {
      const [search, saved] = await Promise.all([
        bookingAwareSearch(Number(distance)),
        apiJson<{ nanny_ids: number[] }>("/parents/me/favorites")
      ]);
      setResults(search.results || []); setFavourites(saved.nanny_ids || []);
    } catch (err) { setError(err instanceof Error ? err.message : "We couldn't load caregivers."); }
    finally { setLoading(false); }
  }
  useEffect(() => {
    Promise.all([
      bookingAwareSearch(10),
      apiJson<{ nanny_ids: number[] }>("/parents/me/favorites"),
      apiJson<{ broadcast_workflow_enabled: boolean }>("/settings/booking-workflow"),
    ]).then(([search, saved, workflow]) => { setResults(search.results || []); setFavourites(saved.nanny_ids || []); setBookingDraft(readBookingDraft()); setBroadcastEnabled(workflow.broadcast_workflow_enabled); })
      .catch((err) => setError(err instanceof Error ? err.message : "We couldn't load caregivers."))
      .finally(() => setLoading(false));
  }, []);

  async function toggleFavourite(id: number) {
    const saved = favourites.includes(id);
    setFavourites((current) => saved ? current.filter((item) => item !== id) : [...current, id]);
    try { await apiJson(`/parents/me/favorites/${id}`, { method: saved ? "DELETE" : "POST" }); }
    catch { setFavourites((current) => saved ? [...current, id] : current.filter((item) => item !== id)); }
  }

  function toggleSelection(id: number) {
    setSelectedNannies((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
  }

  async function broadcastJob() {
    if (!bookingDraft?.slots?.length || !selectedNannies.length) return;
    const requiredCount = Number(bookingDraft.nanniesNeeded || 1);
    if (selectedNannies.length < requiredCount) {
      setBroadcastMessage(`Select at least ${requiredCount} nannies to fill ${requiredCount} positions.`);
      return;
    }
    setSubmitting(true);
    setBroadcastMessage("");
    try {
      const result = await apiJson<{ group_id?: number; created_ids?: number[]; errors?: { nanny_id: number; error: string }[]; requires_payment_method?: boolean; message?: string }>("/booking-requests/bulk", {
        method: "POST",
        body: JSON.stringify({
          nanny_ids: selectedNannies,
          slots: bookingDraft.slots,
          location_id: bookingDraft.locationId ? Number(bookingDraft.locationId) : null,
          kids_count: Number(bookingDraft.kids || 1),
          responsibilities: bookingDraft.responsibilities,
          adult_present: bookingDraft.adultPresent,
          booking_reason: bookingDraft.reason,
          meal_option: bookingDraft.mealOption,
          food_restrictions: bookingDraft.foodRestrictions,
          dogs_info: bookingDraft.dogsInfo,
          sleepover: Boolean(bookingDraft.sleepover),
          sleepover_expectations: bookingDraft.sleepover ? bookingDraft.sleepoverExpectations : null,
          sleepover_reason: bookingDraft.sleepover ? bookingDraft.sleepoverReason : null,
          requested_nannies_count: requiredCount,
          disclaimer_basic_upkeep: true,
          disclaimer_medicine: true,
          disclaimer_extra_hours: true,
          disclaimer_transport: true,
        }),
      });
      if (result.requires_payment_method) {
        setBroadcastMessage(result.message || "Complete Paystack authorisation before broadcasting this job.");
      } else if (result.created_ids?.length) {
        window.sessionStorage.removeItem("my-nanny-booking-draft");
        setBroadcastMessage(`Job sent to ${result.created_ids.length} nannies for ${requiredCount} ${requiredCount === 1 ? "position" : "positions"}. The broadcast remains open until all positions are filled.`);
        setSelectedNannies([]);
        setBookingDraft(null);
      } else {
        setBroadcastMessage(result.errors?.map((item) => item.error).join(", ") || "No booking requests could be sent.");
      }
    } catch (error) {
      setBroadcastMessage(error instanceof Error ? error.message : "Unable to broadcast this job.");
    } finally {
      setSubmitting(false);
    }
  }

  const visible = results.filter((nanny) => nanny.name.toLowerCase().includes(query.toLowerCase()));
  return <AuthenticatedPage>{(role) => role !== "parent" ? <Restricted /> : (
    <div className="mx-auto max-w-6xl">
      <div className="eyebrow">Screened caregivers</div>
      <h1 className="display mt-2 text-4xl sm:text-5xl">Find someone your family can trust.</h1>
      <p className="mt-3 text-[var(--muted)]">Every nanny shown here is approved and has completed their video screening.</p>
      <div className="card mt-7 flex flex-col gap-3 p-4 sm:flex-row">
        <label className="relative flex-1"><Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={18}/><input className="field !pl-11" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search by name"/></label>
        <select className="field sm:max-w-48" value={distance} onChange={(e) => setDistance(e.target.value)} aria-label="Distance"><option value="10">Within 10 km</option><option value="20">Within 20 km</option><option value="30">Within 30 km</option></select>
        <button className="btn-secondary" onClick={load}><MapPin size={17}/>Update results</button>
      </div>
      {bookingDraft?.slots?.length ? <BookingSearchSummary draft={bookingDraft} /> : null}
      {broadcastMessage && <div role="status" className="mt-5 rounded-2xl bg-[var(--blue-pale)] p-4 font-semibold">{broadcastMessage}</div>}
      {loading && <div className="mt-12 flex items-center justify-center gap-2 text-[var(--muted)]"><LoaderCircle className="animate-spin"/>Finding nearby nannies...</div>}
      {error && <div className="mt-6 rounded-2xl border border-amber-200 bg-amber-50 p-5 text-amber-900"><b>We need one more detail.</b><div className="mt-1 text-sm">{error.includes("Location") ? "Add a default home address in your profile before searching." : error}</div></div>}
      {!loading && !error && !visible.length && <div className="card mt-6 p-10 text-center"><h2 className="text-xl font-bold">No screened nannies found in this area</h2><p className="mt-2 text-[var(--muted)]">Try increasing the distance or check again soon.</p></div>}
      <div className="mt-6 grid gap-5 lg:grid-cols-3">{visible.map((nanny) => <NannyCard key={nanny.nanny_id} nanny={nanny} favourite={favourites.includes(nanny.nanny_id)} onFavourite={() => toggleFavourite(nanny.nanny_id)} broadcastMode={Boolean(bookingDraft && broadcastEnabled)} selected={selectedNannies.includes(nanny.nanny_id)} onSelect={() => toggleSelection(nanny.nanny_id)}/>)}</div>
      {bookingDraft && broadcastEnabled && selectedNannies.length > 0 && (
        <div className="sticky bottom-4 z-20 mt-6 flex flex-wrap items-center justify-between gap-4 rounded-3xl border border-[var(--line)] bg-white/95 p-5 shadow-2xl backdrop-blur">
          <div><div className="font-bold">{selectedNannies.length} {selectedNannies.length === 1 ? "nanny" : "nannies"} selected</div><div className="text-sm text-[var(--muted)]">{bookingDraft.nanniesNeeded || "1"} {(bookingDraft.nanniesNeeded || "1") === "1" ? "position" : "positions"} required. Each selected nanny receives the same request.</div></div>
          <button className="btn-primary" disabled={submitting || selectedNannies.length < Number(bookingDraft.nanniesNeeded || 1)} onClick={() => void broadcastJob()}><Radio size={18}/>{submitting ? "Sending..." : `Broadcast job to ${selectedNannies.length}`}</button>
        </div>
      )}
    </div>
  )}</AuthenticatedPage>;
}

function BookingSearchSummary({ draft }: { draft: BookingDraft }) {
  const slots = draft.slots || [];
  return (
    <section className="mt-4 rounded-3xl border border-[var(--line)] bg-[linear-gradient(135deg,var(--blue-pale),#fff)] p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="eyebrow">Your booking request</div>
          <h2 className="mt-2 text-xl font-bold">Nannies available for these dates</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">Every nanny below is available for all selected time slots.</p>
        </div>
        <Link href="/bookings?edit=1" className="btn-secondary"><Pencil size={16} />Edit booking details</Link>
      </div>
      <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {slots.map((slot, index) => {
          const start = new Date(slot.starts_at);
          const end = new Date(slot.ends_at);
          return (
            <div className="rounded-2xl bg-white p-4 shadow-sm" key={`${slot.starts_at}-${index}`}>
              <div className="flex items-center gap-2 font-bold"><CalendarDays size={17} className="text-[var(--blue-dark)]" />{start.toLocaleDateString("en-ZA", { weekday: "short", day: "numeric", month: "long", year: "numeric" })}</div>
              <div className="mt-2 flex items-center gap-2 text-sm text-[var(--muted)]"><Clock size={15} />{start.toLocaleTimeString("en-ZA", { hour: "2-digit", minute: "2-digit" })} - {end.toLocaleTimeString("en-ZA", { hour: "2-digit", minute: "2-digit" })}</div>
            </div>
          );
        })}
      </div>
      <div className="mt-4 flex items-center gap-2 text-sm font-semibold"><MapPin size={16} className="text-[var(--coral)]" />{draft.locationLabel || "Your selected booking address"}</div>
      <div className="mt-2 text-sm font-semibold">{draft.nanniesNeeded || "1"} {(draft.nanniesNeeded || "1") === "1" ? "nanny" : "nannies"} needed</div>
    </section>
  );
}

export function NannyCard({ nanny, favourite, onFavourite, broadcastMode = false, selected = false, onSelect }: { nanny: NannyResult; favourite: boolean; onFavourite: () => void; broadcastMode?: boolean; selected?: boolean; onSelect?: () => void }) {
  const badges = nanny.trust_badges || [];
  return <article className="card overflow-hidden">
    <div className="relative flex aspect-[4/3] items-center justify-center bg-[linear-gradient(145deg,#d6edf6,#f1f9fb)]">
      {nanny.profile_photo_url ? <Image src={nanny.profile_photo_url} alt={nanny.name} fill className="object-cover" unoptimized/> : <button className="flex flex-col items-center text-[var(--blue-dark)]"><PlayCircle size={54}/><span className="mt-2 text-sm font-bold">Video introduction complete</span></button>}
      <button aria-label={`${favourite ? "Remove" : "Add"} ${nanny.name} ${favourite ? "from" : "to"} favourites`} onClick={onFavourite} className="absolute right-4 top-4 flex h-11 w-11 items-center justify-center rounded-full bg-white shadow"><Heart size={19} fill={favourite ? "#dc765f" : "none"} color={favourite ? "#dc765f" : "currentColor"}/></button>
    </div>
    <div className="p-5"><div className="flex items-start justify-between gap-3"><div><h2 className="text-xl font-bold">{nanny.name}</h2><div className="mt-1 flex items-center gap-1 text-sm text-[var(--muted)]"><MapPin size={14}/>{nanny.distance_km != null ? `${nanny.distance_km.toFixed(1)} km away` : nanny.location_hint || "Location available"}</div></div><span className="pill"><Star size={13} fill={nanny.average_rating_12m == null ? "none" : "#e5aa45"} color="#e5aa45"/>{nanny.average_rating_12m?.toFixed(1) || "New"}</span></div>
      <p className="mt-4 line-clamp-3 text-sm leading-6 text-[var(--muted)]">{nanny.profile_summary || "A screened My Nanny caregiver ready to meet your family."}</p>
      <div className="mt-4 flex flex-wrap gap-2">{badges.map((badge) => <span className="pill" key={badge.key}><BadgeCheck size={13} className="text-[var(--green)]"/>{badge.label}</span>)}</div>
      <div className="mt-5 border-t border-[var(--line)] pt-4 text-sm text-[var(--muted)]">{nanny.completed_jobs_count || 0} completed jobs · {nanny.review_count_12m || 0} family reviews</div>
      {broadcastMode ? <button className={`${selected ? "btn-primary" : "btn-secondary"} mt-4 w-full`} onClick={onSelect}>{selected ? <Check size={17}/> : null}{selected ? "Selected for broadcast" : "Add to broadcast"}</button> : <Link className="btn-primary mt-4 w-full" href={`/bookings?nanny=${nanny.nanny_id}`}>Select this nanny</Link>}
    </div>
  </article>;
}

function Restricted(){return <div className="card mx-auto max-w-xl p-8 text-center"><BadgeCheck className="mx-auto text-[var(--blue-dark)]" size={34}/><h1 className="mt-4 text-2xl font-bold">Parent access only</h1><p className="mt-2 text-[var(--muted)]">Caregiver browsing is available to verified parent accounts.</p></div>}
