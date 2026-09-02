"use client";

import { apiJson } from "@/lib/api";
import {
  BriefcaseBusiness,
  Check,
  LoaderCircle,
  ShieldCheck,
} from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import {
  PlacementField,
  PlacementHeading,
  PlacementInfo,
  PlacementNotice,
} from "./shared";
import { InterviewCommunication } from "./communication";
import { dateTime, money, niceStatus } from "./types";

type NannyPreference = {
  opted_in: boolean;
  desired_salary_min_cents?: number | null;
  desired_salary_max_cents?: number | null;
  employment_types: string[];
  preferred_locations?: string | null;
  available_from?: string | null;
  live_in_preference?: string | null;
  profile_notes?: string | null;
};

type Opportunity = {
  candidate_id: number;
  placement_id: number;
  status: string;
  consent_status: string;
  service_tier: string;
  role_title: string;
  employment_type: string;
  start_date?: string | null;
  schedule_summary: string;
  children_count: number;
  children_ages: string[];
  duties: string;
  special_requirements?: string | null;
  salary_min_cents: number;
  salary_max_cents: number;
  broad_location: string;
  live_in: boolean;
  drivers_license_required: boolean;
  own_car_required: boolean;
  languages: string[];
  pets?: string | null;
  interview_scheduled_at?: string | null;
  interview_invite_status: string;
  interview_responded_at?: string | null;
  interview_checked_in_at?: string | null;
  interview_completed_at?: string | null;
  interview_format?: string | null;
  interview_location?: string | null;
  trial_scheduled_at?: string | null;
  trial_ends_at?: string | null;
  trial_status?: string | null;
  trial_alternative_at?: string | null;
  trial_notes?: string | null;
  offer_status?: string | null;
  offer_salary_cents?: number | null;
  offer_start_date?: string | null;
  offer_working_days?: number[];
  offer_start_time?: string | null;
  offer_end_time?: string | null;
  offer_terms?: string | null;
  availability_restructured_at?: string | null;
};

const weekdayNames = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export function NannyPermanentPlacements() {
  const [profile, setProfile] = useState<NannyPreference | null>(null);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState("");
  const [trialAlternatives, setTrialAlternatives] = useState<Record<number, string>>({});
  const [supportNotes, setSupportNotes] = useState<Record<number, string>>({});
  const [form, setForm] = useState({
    opted_in: false,
    min: "",
    max: "",
    employment_types: ["full_time"] as string[],
    preferred_locations: "",
    available_from: "",
    live_in_preference: "either",
    profile_notes: "",
  });

  async function load() {
    const [preference, rows] = await Promise.all([
      apiJson<NannyPreference>("/nannies/me/permanent-placement-profile"),
      apiJson<{ results: Opportunity[] }>("/nannies/me/permanent-opportunities"),
    ]);
    setProfile(preference);
    setOpportunities(rows.results || []);
    setForm({
      opted_in: preference.opted_in,
      min: preference.desired_salary_min_cents
        ? String(preference.desired_salary_min_cents / 100)
        : "",
      max: preference.desired_salary_max_cents
        ? String(preference.desired_salary_max_cents / 100)
        : "",
      employment_types: preference.employment_types?.length
        ? preference.employment_types
        : ["full_time"],
      preferred_locations: preference.preferred_locations || "",
      available_from: preference.available_from || "",
      live_in_preference: preference.live_in_preference || "either",
      profile_notes: preference.profile_notes || "",
    });
  }

  useEffect(() => {
    Promise.all([
      apiJson<NannyPreference>("/nannies/me/permanent-placement-profile"),
      apiJson<{ results: Opportunity[] }>("/nannies/me/permanent-opportunities"),
    ])
      .then(([preference, rows]) => {
        setProfile(preference);
        setOpportunities(rows.results || []);
        setForm({
          opted_in: preference.opted_in,
          min: preference.desired_salary_min_cents
            ? String(preference.desired_salary_min_cents / 100)
            : "",
          max: preference.desired_salary_max_cents
            ? String(preference.desired_salary_max_cents / 100)
            : "",
          employment_types: preference.employment_types?.length
            ? preference.employment_types
            : ["full_time"],
          preferred_locations: preference.preferred_locations || "",
          available_from: preference.available_from || "",
          live_in_preference: preference.live_in_preference || "either",
          profile_notes: preference.profile_notes || "",
        });
      })
      .catch((error) =>
        setMessage(
          error instanceof Error
            ? error.message
            : "Unable to load permanent opportunities.",
        ),
      );
  }, []);

  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy("save");
    try {
      await apiJson("/nannies/me/permanent-placement-profile", {
        method: "PUT",
        body: JSON.stringify({
          opted_in: form.opted_in,
          desired_salary_min_cents: form.min
            ? Math.round(Number(form.min) * 100)
            : null,
          desired_salary_max_cents: form.max
            ? Math.round(Number(form.max) * 100)
            : null,
          employment_types: form.employment_types,
          preferred_locations: form.preferred_locations || null,
          available_from: form.available_from || null,
          live_in_preference: form.live_in_preference,
          profile_notes: form.profile_notes || null,
        }),
      });
      setMessage(
        form.opted_in
          ? "You are opted into permanent opportunities. You still approve every family search before your profile is shared."
          : "You have opted out of new permanent opportunities.",
      );
      await load();
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Unable to save preferences.",
      );
    } finally {
      setBusy("");
    }
  }

  async function respond(candidateId: number, decision: "accepted" | "declined") {
    setBusy(`${decision}-${candidateId}`);
    try {
      await apiJson(
        `/nannies/me/permanent-opportunities/${candidateId}/respond`,
        {
          method: "POST",
          body: JSON.stringify({ decision, note: null }),
        },
      );
      setMessage(
        decision === "accepted"
          ? "Consent recorded. Admin may now share your privacy-safe profile with this family."
          : "Opportunity declined. Your profile was not shared.",
      );
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to respond.");
    } finally {
      setBusy("");
    }
  }

  async function respondToInterview(candidateId: number, decision: "accepted" | "declined" | "cancelled") {
    const note = decision === "cancelled" ? window.prompt("Please tell My Nanny why you need to cancel this interview") : null;
    if (decision === "cancelled" && !note) return;
    setBusy(`interview-${decision}-${candidateId}`);
    try {
      await apiJson(`/nannies/me/permanent-opportunities/${candidateId}/interview-response`, {
        method: "POST",
        body: JSON.stringify({ decision, note }),
      });
      setMessage(
        decision === "accepted"
          ? "Interview accepted. My Nanny will coordinate the date and arrangements."
          : decision === "cancelled"
            ? "Interview cancelled and the family's interview credit was restored."
            : "Interview invitation declined. No family credit was used.",
      );
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to respond to the interview.");
    } finally {
      setBusy("");
    }
  }

  async function updateInterview(candidateId: number, action: "check_in" | "completed") {
    setBusy(`interview-${action}-${candidateId}`);
    try {
      await apiJson(`/nannies/me/permanent-opportunities/${candidateId}/interview-progress`, {
        method: "POST",
        body: JSON.stringify({ action }),
      });
      setMessage(action === "check_in" ? "Arrival confirmed. The family and My Nanny have been notified." : "Interview completed. The family can now record feedback and choose the next step.");
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to update the interview.");
    } finally {
      setBusy("");
    }
  }

  async function respondToTrial(candidateId: number, decision: "accepted" | "declined" | "change_requested") {
    const alternative = trialAlternatives[candidateId] || null;
    if (decision === "change_requested" && !alternative) {
      setMessage("Choose the alternative trial date and time first.");
      return;
    }
    setBusy(`trial-${decision}-${candidateId}`);
    try {
      await apiJson(`/nannies/me/permanent-opportunities/${candidateId}/trial-response`, {
        method: "POST",
        body: JSON.stringify({ decision, alternative_at: alternative, note: null }),
      });
      setMessage(decision === "accepted" ? "Trial accepted. The family and My Nanny have been notified." : decision === "change_requested" ? "Your suggested time was sent to the family." : "Trial declined. My Nanny will support the next step.");
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to respond to the trial.");
    } finally {
      setBusy("");
    }
  }

  async function respondToOffer(candidateId: number, decision: "accepted" | "declined" | "admin_support") {
    const note = (supportNotes[candidateId] || "").trim();
    if (decision === "admin_support" && !note) {
      setMessage("Tell My Nanny what you would like to discuss first.");
      return;
    }
    setBusy(`offer-${decision}-${candidateId}`);
    try {
      await apiJson(`/nannies/me/permanent-opportunities/${candidateId}/offer-response`, {
        method: "POST",
        body: JSON.stringify({ decision, note: note || null }),
      });
      setMessage(decision === "accepted" ? "Offer accepted. Your calendar is now available only outside the agreed permanent working schedule." : decision === "admin_support" ? "My Nanny has been asked to contact you about the offer." : "Offer declined. The family and My Nanny have been notified.");
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to respond to the offer.");
    } finally {
      setBusy("");
    }
  }

  function toggleType(value: string) {
    setForm({
      ...form,
      employment_types: form.employment_types.includes(value)
        ? form.employment_types.filter((item) => item !== value)
        : [...form.employment_types, value],
    });
  }

  if (!profile)
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <LoaderCircle className="animate-spin" />
      </div>
    );

  return (
    <div className="mx-auto max-w-7xl">
      <PlacementHeading
        eyebrow="Long-term opportunities"
        title="Permanent placements."
        body="Tell us what long-term work suits you. Your contact details and documents stay private, and you approve every family search before your profile is shared."
      />
      <PlacementNotice message={message} />
      <div className="mt-8 grid gap-7 xl:grid-cols-[.82fr_1.18fr]">
        <form className="card p-6 sm:p-8" onSubmit={save}>
          <div className="flex items-start justify-between gap-4">
            <div><div className="eyebrow">Your choice</div><h2 className="mt-2 text-2xl font-bold">Permanent work profile</h2></div>
            <label className="flex cursor-pointer items-center gap-3 rounded-full border border-[var(--line)] px-4 py-2 text-sm font-bold">
              <input type="checkbox" checked={form.opted_in} onChange={(event) => setForm({ ...form, opted_in: event.target.checked })} />
              {form.opted_in ? "Opted in" : "Opted out"}
            </label>
          </div>
          <div className="mt-6 grid gap-5 sm:grid-cols-2">
            <PlacementField label="Monthly salary from"><input className="field" type="number" min="1" value={form.min} onChange={(event) => setForm({ ...form, min: event.target.value })} /></PlacementField>
            <PlacementField label="Monthly salary to"><input className="field" type="number" min="1" value={form.max} onChange={(event) => setForm({ ...form, max: event.target.value })} /></PlacementField>
            <PlacementField label="Available from"><input className="field" type="date" value={form.available_from} onChange={(event) => setForm({ ...form, available_from: event.target.value })} /></PlacementField>
            <PlacementField label="Live-in preference"><select className="field" value={form.live_in_preference} onChange={(event) => setForm({ ...form, live_in_preference: event.target.value })}><option value="either">Either</option><option value="yes">Prefer live-in</option><option value="no">Live-out only</option></select></PlacementField>
            <div className="sm:col-span-2"><div className="mb-2 text-sm font-bold">Employment types</div><div className="flex flex-wrap gap-2">{["full_time", "part_time", "live_in", "live_out"].map((value) => <button type="button" key={value} className={form.employment_types.includes(value) ? "btn-primary !min-h-9" : "btn-secondary !min-h-9"} onClick={() => toggleType(value)}>{niceStatus(value)}</button>)}</div></div>
            <PlacementField label="Preferred areas"><textarea className="field min-h-20" value={form.preferred_locations} onChange={(event) => setForm({ ...form, preferred_locations: event.target.value })} placeholder="Sandton, Midrand, Centurion" /></PlacementField>
            <PlacementField label="Notes for the placement team"><textarea className="field min-h-20" value={form.profile_notes} onChange={(event) => setForm({ ...form, profile_notes: event.target.value })} /></PlacementField>
          </div>
          <div className="mt-6 rounded-2xl bg-[var(--blue-pale)] p-4 text-sm leading-6"><b>Your privacy is protected.</b> Families see your first name, candidate number, broad location, experience and verification status. Phone numbers, ID details, home addresses and references remain private.</div>
          <button className="btn-primary mt-6 w-full" disabled={busy === "save"}>{busy === "save" ? <LoaderCircle className="animate-spin" size={17} /> : <ShieldCheck size={17} />}Save preferences</button>
        </form>
        <section>
          <div className="flex items-center justify-between"><div><div className="eyebrow">Family searches</div><h2 className="mt-2 text-3xl font-bold">Your opportunities</h2></div><span className="pill">{opportunities.length}</span></div>
          {opportunities.length ? (
            <div className="mt-5 grid gap-4">
              {opportunities.map((row) => (
                <article className="card p-6" key={row.candidate_id}>
                  <div className="flex flex-wrap items-start justify-between gap-3"><div><div className="eyebrow">Family in {row.broad_location}</div><h3 className="mt-2 text-2xl font-bold">{row.role_title}</h3><div className="mt-2 text-sm text-[var(--muted)]">{niceStatus(row.employment_type)} · {money(row.salary_min_cents)} - {money(row.salary_max_cents)} monthly</div></div><span className="pill">{niceStatus(row.consent_status)}</span></div>
                  <div className="mt-5 grid gap-4 rounded-2xl bg-[var(--blue-pale)] p-5 sm:grid-cols-2"><PlacementInfo label="Schedule" value={row.schedule_summary} /><PlacementInfo label="Children" value={`${row.children_count} · ${row.children_ages.join(", ") || "Ages to confirm"}`} /><PlacementInfo label="Duties" value={row.duties} /><PlacementInfo label="Requirements" value={opportunityRequirements(row)} /></div>
                  {row.consent_status === "pending" && <div className="mt-5 flex flex-wrap gap-3"><button className="btn-primary" disabled={Boolean(busy)} onClick={() => void respond(row.candidate_id, "accepted")}><Check size={17} />I am interested</button><button className="btn-secondary" disabled={Boolean(busy)} onClick={() => void respond(row.candidate_id, "declined")}>Not for me</button></div>}
                  {row.interview_invite_status === "pending" && <div className="mt-5 rounded-2xl border border-[var(--line)] p-5"><b>Interview invitation</b><p className="mt-2 text-sm text-[var(--muted)]">Accept only if you would like My Nanny to arrange this interview.</p><div className="mt-4 flex flex-wrap gap-3"><button className="btn-primary" disabled={Boolean(busy)} onClick={() => void respondToInterview(row.candidate_id, "accepted")}><Check size={17} />Accept interview</button><button className="btn-secondary" disabled={Boolean(busy)} onClick={() => void respondToInterview(row.candidate_id, "declined")}>Decline</button></div></div>}
                  {row.interview_invite_status === "accepted" && !row.interview_scheduled_at && <div className="mt-5 rounded-2xl bg-[var(--blue-pale)] p-4 text-sm"><b>Interview accepted.</b> My Nanny is arranging the details. <button className="ml-2 font-bold underline" disabled={Boolean(busy)} onClick={() => void respondToInterview(row.candidate_id, "cancelled")}>Cancel interview</button></div>}
                  {row.interview_scheduled_at && <div className="mt-5 rounded-2xl border border-[var(--line)] p-4 text-sm"><b>Interview:</b> {dateTime(row.interview_scheduled_at)} · {niceStatus(row.interview_format || "")}{row.interview_location ? ` · ${row.interview_location}` : ""}{!row.interview_completed_at && <div className="mt-4 flex flex-wrap gap-3">{!row.interview_checked_in_at && <button className="btn-secondary !min-h-9" disabled={Boolean(busy)} onClick={() => void updateInterview(row.candidate_id, "check_in")}>I have arrived</button>}<button className="btn-primary !min-h-9" disabled={Boolean(busy)} onClick={() => void updateInterview(row.candidate_id, "completed")}><Check size={17} />Interview completed</button></div>}{row.interview_checked_in_at && !row.interview_completed_at && <p className="mt-3 font-semibold text-[var(--green)]">Arrival confirmed</p>}{row.interview_completed_at && <p className="mt-3 font-semibold text-[var(--green)]">Interview completed</p>}</div>}
                  {row.interview_invite_status === "accepted" && row.interview_scheduled_at && <button className="btn-quiet mt-3 text-sm" disabled={Boolean(busy)} onClick={() => void respondToInterview(row.candidate_id, "cancelled")}>I need to cancel this interview</button>}
                  {["accepted", "completed"].includes(row.interview_invite_status) && <InterviewCommunication candidateId={row.candidate_id} />}
                  {row.trial_status && row.trial_status !== "not_requested" && (
                    <div className="mt-5 rounded-2xl border border-[var(--line)] p-5">
                      <div className="flex flex-wrap items-center justify-between gap-2"><b>Paid trial request</b><span className="pill">{niceStatus(row.trial_status)}</span></div>
                      <p className="mt-3 text-sm leading-6 text-[var(--muted)]">{dateTime(row.trial_scheduled_at)} to {dateTime(row.trial_ends_at)}</p>
                      {row.trial_notes && <p className="mt-2 text-sm leading-6">{row.trial_notes}</p>}
                      {row.trial_status === "pending" && (
                        <div className="mt-4 grid gap-3">
                          <div className="flex flex-wrap gap-3"><button className="btn-primary !min-h-9" disabled={Boolean(busy)} onClick={() => void respondToTrial(row.candidate_id, "accepted")}><Check size={17} />Accept trial</button><button className="btn-secondary !min-h-9" disabled={Boolean(busy)} onClick={() => void respondToTrial(row.candidate_id, "declined")}>Decline</button></div>
                          <div className="grid gap-2 sm:grid-cols-[1fr_auto]"><input className="field" type="datetime-local" value={trialAlternatives[row.candidate_id] || ""} onChange={(event) => setTrialAlternatives({ ...trialAlternatives, [row.candidate_id]: event.target.value })} /><button className="btn-secondary" disabled={Boolean(busy) || !trialAlternatives[row.candidate_id]} onClick={() => void respondToTrial(row.candidate_id, "change_requested")}>Suggest another time</button></div>
                        </div>
                      )}
                    </div>
                  )}
                  {row.offer_status && row.offer_status !== "not_requested" && (
                    <div className="mt-5 rounded-2xl bg-[var(--blue-pale)] p-5">
                      <div className="flex flex-wrap items-center justify-between gap-2"><b>Permanent employment offer</b><span className="pill">{niceStatus(row.offer_status)}</span></div>
                      <div className="mt-4 grid gap-2 text-sm leading-6">
                        <span><b>Monthly salary:</b> {money(row.offer_salary_cents)}</span>
                        <span><b>Start date:</b> {row.offer_start_date || "To confirm"}</span>
                        <span><b>Working days:</b> {(row.offer_working_days || []).map((day) => weekdayNames[day]).join(", ")}</span>
                        <span><b>Working times:</b> {row.offer_start_time}-{row.offer_end_time}</span>
                        {row.offer_terms && <span><b>Terms:</b> {row.offer_terms}</span>}
                      </div>
                      {row.offer_status === "pending" && (
                        <div className="mt-4 grid gap-3">
                          <div className="flex flex-wrap gap-3"><button className="btn-primary" disabled={Boolean(busy)} onClick={() => void respondToOffer(row.candidate_id, "accepted")}><Check size={17} />Accept offer</button><button className="btn-secondary" disabled={Boolean(busy)} onClick={() => void respondToOffer(row.candidate_id, "declined")}>Decline</button></div>
                          <textarea className="field min-h-20 bg-white" value={supportNotes[row.candidate_id] || ""} onChange={(event) => setSupportNotes({ ...supportNotes, [row.candidate_id]: event.target.value })} placeholder="Questions about salary, duties or the working arrangement" />
                          <button className="btn-secondary" disabled={Boolean(busy) || !(supportNotes[row.candidate_id] || "").trim()} onClick={() => void respondToOffer(row.candidate_id, "admin_support")}>Ask My Nanny to contact me</button>
                        </div>
                      )}
                      {row.offer_status === "accepted" && <p className="mt-4 text-sm font-semibold text-[var(--green)]">Accepted. Your weekday short-term availability has been restructured around this role; free days such as weekends remain available for bookings.</p>}
                    </div>
                  )}
                </article>
              ))}
            </div>
          ) : (
            <div className="card mt-5 p-10 text-center"><BriefcaseBusiness className="mx-auto text-[var(--blue)]" size={36} /><h3 className="mt-4 text-xl font-bold">No permanent opportunities yet</h3><p className="mt-2 text-sm text-[var(--muted)]">When a family search suits your profile, it will appear here for your approval.</p></div>
          )}
        </section>
      </div>
    </div>
  );
}

function opportunityRequirements(row: Opportunity) {
  return [
    row.live_in && "Live-in",
    row.drivers_license_required && "Driver's licence",
    row.own_car_required && "Own car",
    row.special_requirements,
  ].filter(Boolean).join(" · ") || "No additional requirements";
}
