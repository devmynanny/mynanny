"use client";

import { apiJson } from "@/lib/api";
import {
  ArrowRight,
  Banknote,
  CalendarDays,
  Check,
  CheckCircle2,
  Clock3,
  Handshake,
  LoaderCircle,
  MapPin,
  Search,
  ShieldCheck,
  Sparkles,
  UserRoundCheck,
} from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import {
  PlacementField,
  PlacementHeading,
  PlacementInfo,
  PlacementNotice,
} from "./shared";
import { Candidate, Config, money, niceStatus, Placement } from "./types";

const emptyBrief = {
  role_title: "Permanent nanny",
  employment_type: "full_time",
  start_date: "",
  schedule_summary: "Monday to Friday, 07:00 to 17:00",
  hours_per_week: "45",
  children_count: "1",
  children_ages: "",
  duties: "Childcare, age-appropriate activities, meals and the children's routine",
  special_requirements: "",
  salary_min: "6000",
  salary_max: "9000",
  location_suburb: "",
  location_city: "",
  location_province: "Gauteng",
  live_in: false,
  drivers_license_required: false,
  own_car_required: false,
  languages: "",
  pets: "",
};

export function ParentPermanentPlacements() {
  const [config, setConfig] = useState<Config | null>(null);
  const [placements, setPlacements] = useState<Placement[]>([]);
  const [selected, setSelected] = useState<Placement | null>(null);
  const [tier, setTier] = useState<"self_match" | "concierge" | null>(null);
  const [brief, setBrief] = useState(emptyBrief);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");

  async function load(selectId?: number) {
    const [nextConfig, list] = await Promise.all([
      apiJson<Config>("/permanent-placements/config"),
      apiJson<{ results: Placement[] }>("/parents/me/permanent-placements"),
    ]);
    setConfig(nextConfig);
    setPlacements(list.results || []);
    const id = selectId || selected?.id;
    if (id) {
      setSelected(
        await apiJson<Placement>(`/parents/me/permanent-placements/${id}`),
      );
    }
  }

  useEffect(() => {
    Promise.all([
      apiJson<Config>("/permanent-placements/config"),
      apiJson<{ results: Placement[] }>("/parents/me/permanent-placements"),
    ])
      .then(([nextConfig, list]) => {
        setConfig(nextConfig);
        setPlacements(list.results || []);
      })
      .catch((error) =>
        setMessage(
          error instanceof Error
            ? error.message
            : "Unable to load permanent placements.",
        ),
      )
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const reference = params.get("reference");
    const placementId = Number(params.get("placement_id"));
    if (
      !reference ||
      !placementId ||
      params.get("placement_payment") !== "verify"
    )
      return;
    apiJson<Placement>(
      `/parents/me/permanent-placements/${placementId}/payments/verify`,
      { method: "POST", body: JSON.stringify({ reference }) },
    )
      .then((detail) => {
        setSelected(detail);
        setMessage("Payment confirmed. Your search has moved to the next step.");
        window.history.replaceState({}, "", "/placements");
      })
      .catch((error) =>
        setMessage(
          error instanceof Error ? error.message : "Unable to verify payment.",
        ),
      )
  }, []);

  async function createBrief(event: FormEvent) {
    event.preventDefault();
    if (!tier) return;
    setBusy("create");
    setMessage("");
    try {
      const created = await apiJson<Placement>(
        "/parents/me/permanent-placements",
        {
          method: "POST",
          body: JSON.stringify({
            service_tier: tier,
            role_title: brief.role_title,
            employment_type: brief.employment_type,
            start_date: brief.start_date || null,
            schedule_summary: brief.schedule_summary,
            hours_per_week: Number(brief.hours_per_week) || null,
            children_count: Number(brief.children_count),
            children_ages: splitList(brief.children_ages),
            duties: brief.duties,
            special_requirements: brief.special_requirements || null,
            salary_min_cents: Math.round(Number(brief.salary_min) * 100),
            salary_max_cents: Math.round(Number(brief.salary_max) * 100),
            location_suburb: brief.location_suburb,
            location_city: brief.location_city,
            location_province: brief.location_province || null,
            live_in: brief.live_in,
            drivers_license_required: brief.drivers_license_required,
            own_car_required: brief.own_car_required,
            languages: splitList(brief.languages),
            pets: brief.pets || null,
          }),
        },
      );
      setSelected(created);
      setTier(null);
      setMessage(
        "Your brief is saved. Complete the opening fee when you are ready to submit it.",
      );
      await load(created.id);
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Unable to create the placement brief.",
      );
    } finally {
      setBusy("");
    }
  }

  async function pay(feeType: string) {
    if (!selected) return;
    setBusy(`pay-${feeType}`);
    try {
      const callback = new URL("/placements", window.location.origin);
      callback.searchParams.set("placement_payment", "verify");
      callback.searchParams.set("placement_id", String(selected.id));
      const result = await apiJson<{ authorization_url?: string }>(
        `/parents/me/permanent-placements/${selected.id}/payments/${feeType}/initialize`,
        {
          method: "POST",
          body: JSON.stringify({ callback_url: callback.toString() }),
        },
      );
      if (!result.authorization_url)
        throw new Error("Paystack did not provide a secure payment page.");
      window.location.assign(result.authorization_url);
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Unable to start payment.",
      );
      setBusy("");
    }
  }

  async function candidateAction(
    candidateId: number,
    action: "shortlist" | "request-interview",
  ) {
    if (!selected) return;
    setBusy(`${action}-${candidateId}`);
    try {
      setSelected(
        await apiJson<Placement>(
          `/parents/me/permanent-placements/${selected.id}/candidates/${candidateId}/${action}`,
          { method: "POST", body: JSON.stringify({ note: null }) },
        ),
      );
      setMessage(
        action === "shortlist"
          ? "Candidate added to your shortlist."
          : "Interview request sent to the placement team.",
      );
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to update candidate.");
    } finally {
      setBusy("");
    }
  }

  async function upgrade() {
    if (!selected) return;
    setBusy("upgrade");
    try {
      setSelected(
        await apiJson<Placement>(
          `/parents/me/permanent-placements/${selected.id}/upgrade`,
          { method: "POST", body: "{}" },
        ),
      );
      setMessage("Your search is now a managed Concierge placement.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to upgrade.");
    } finally {
      setBusy("");
    }
  }

  async function requestReplacement() {
    if (!selected) return;
    const reason = window.prompt(
      "Please explain why you need a replacement or profile rematch.",
    );
    if (!reason) return;
    setBusy("replacement");
    try {
      setSelected(
        await apiJson<Placement>(
          `/parents/me/permanent-placements/${selected.id}/request-replacement`,
          { method: "POST", body: JSON.stringify({ reason }) },
        ),
      );
      setMessage("Your request has been sent to the placement team for review.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to send the request.");
    } finally {
      setBusy("");
    }
  }

  if (loading || !config)
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <LoaderCircle className="animate-spin text-[var(--blue-dark)]" />
      </div>
    );

  if (selected)
    return (
      <ParentPlacementDetail
        placement={selected}
        busy={busy}
        message={message}
        onBack={() => setSelected(null)}
        onPay={pay}
        onUpgrade={upgrade}
        onRequestReplacement={requestReplacement}
        onCandidateAction={candidateAction}
      />
    );

  return (
    <div className="mx-auto max-w-7xl">
      <PlacementHeading
        eyebrow="Long-term care"
        title="Find the right long-term match."
        body="Choose your own nanny shortlist, or let our placement team manage the search from family brief to onboarding."
      />
      <PlacementNotice message={message} />
      {placements.length > 0 && (
        <section className="mt-8">
          <div className="mb-4 text-sm font-bold">Your existing searches</div>
          <div className="grid gap-3">
            {placements.map((placement) => (
              <button
                key={placement.id}
                onClick={() => void load(placement.id)}
                className="card flex w-full items-center justify-between p-5 text-left transition hover:-translate-y-0.5"
              >
                <span>
                  <b className="block">{placement.role_title}</b>
                  <span className="mt-1 block text-sm text-[var(--muted)]">
                    {niceStatus(placement.service_tier)} · {placement.location_suburb} · {niceStatus(placement.status)}
                  </span>
                </span>
                <ArrowRight size={18} />
              </button>
            ))}
          </div>
        </section>
      )}
      {!config.enabled && (
        <div className="card mt-8 border-amber-200 bg-[#fffaf0] p-7">
          <div className="eyebrow !text-amber-800">Pilot preparing</div>
          <h2 className="mt-2 text-2xl font-bold">New family briefs are not open yet.</h2>
          <p className="mt-2 text-[var(--muted)]">
            Admin can open the pilot when the placement team is ready. Existing searches remain available.
          </p>
        </div>
      )}
      <div className="mt-8 grid gap-6 lg:grid-cols-2">
        <OfferCard
          title="Self-Match"
          subtitle="You build the shortlist"
          total={config.pricing.self_match.total_if_placed_cents}
          selected={tier === "self_match"}
          disabled={!config.enabled}
          onSelect={() => setTier("self_match")}
          points={[
            `${money(config.pricing.self_match.activation_fee_cents)} search activation`,
            `${config.pricing.self_match.profile_limit} profiles and ${config.pricing.self_match.interview_limit} interviews`,
            `${config.pricing.self_match.rematch_days}-day profile rematch`,
            "Contact details stay protected",
          ]}
        />
        <OfferCard
          title="Concierge Placement"
          subtitle="We manage the search"
          total={config.pricing.concierge.total_if_placed_cents}
          selected={tier === "concierge"}
          disabled={!config.enabled}
          onSelect={() => setTier("concierge")}
          points={[
            `${money(config.pricing.concierge.application_fee_cents)} application`,
            `Curated shortlist and ${config.pricing.concierge.interview_limit} interviews`,
            "Interview, trial and onboarding coordination",
            `One replacement within ${config.pricing.concierge.replacement_days} days`,
          ]}
          concierge
        />
      </div>
      {tier && (
        <PlacementBriefForm
          brief={brief}
          setBrief={setBrief}
          busy={busy === "create"}
          onCancel={() => setTier(null)}
          onSubmit={createBrief}
        />
      )}
    </div>
  );
}

function ParentPlacementDetail({
  placement,
  busy,
  message,
  onBack,
  onPay,
  onUpgrade,
  onRequestReplacement,
  onCandidateAction,
}: {
  placement: Placement;
  busy: string;
  message: string;
  onBack: () => void;
  onPay: (fee: string) => void;
  onUpgrade: () => void;
  onRequestReplacement: () => void;
  onCandidateAction: (
    id: number,
    action: "shortlist" | "request-interview",
  ) => void;
}) {
  const dueFeeType =
    placement.status === "awaiting_initial_payment"
      ? placement.service_tier === "self_match"
        ? "activation"
        : "application"
      : placement.status === "awaiting_candidate_access"
        ? "candidate_access"
        : placement.status === "awaiting_success_fee"
          ? "success"
          : null;
  const pendingPayment = dueFeeType
    ? placement.payments.find(
        (row) => row.fee_type === dueFeeType && row.status !== "paid",
      )
    : undefined;
  return (
    <div className="mx-auto max-w-7xl">
      <div className="flex flex-wrap items-start justify-between gap-5">
        <PlacementHeading
          eyebrow="Permanent care"
          title={placement.role_title}
          body={`${niceStatus(placement.service_tier)} placement in ${placement.location_suburb}. Track every protected introduction, interview and payment here.`}
        />
        <button className="btn-secondary" onClick={onBack}>View all searches</button>
      </div>
      <PlacementNotice message={message} />
      <div className="mt-8 grid gap-6 xl:grid-cols-[1.15fr_.85fr]">
        <section className="card overflow-hidden">
          <div className="bg-[linear-gradient(135deg,var(--blue-dark),#4e91af)] p-7 text-white">
            <div className="flex justify-between gap-3">
              <span className="text-xs font-extrabold uppercase tracking-[.18em] text-white/65">Search #{placement.id}</span>
              <span className="rounded-full bg-white/15 px-3 py-1.5 text-xs font-bold">{niceStatus(placement.status)}</span>
            </div>
            <h2 className="mt-5 text-3xl font-bold">{placement.children_count} {placement.children_count === 1 ? "child" : "children"}</h2>
            <div className="mt-4 grid gap-2 text-sm text-white/80 sm:grid-cols-2">
              <span className="flex gap-2"><MapPin size={17} />{placement.location_suburb}, {placement.location_city}</span>
              <span className="flex gap-2"><Banknote size={17} />{money(placement.salary_min_cents)} - {money(placement.salary_max_cents)} monthly</span>
              <span className="flex gap-2"><CalendarDays size={17} />{placement.start_date || "Flexible start"}</span>
              <span className="flex gap-2"><Clock3 size={17} />{placement.hours_per_week ? `${placement.hours_per_week} hours weekly` : "Hours to confirm"}</span>
            </div>
          </div>
          <div className="grid gap-5 p-7 sm:grid-cols-2">
            <PlacementInfo label="Schedule" value={placement.schedule_summary} />
            <PlacementInfo label="Duties" value={placement.duties} />
            <PlacementInfo label="Children's ages" value={placement.children_ages.join(", ") || "Not specified"} />
            <PlacementInfo label="Requirements" value={requirements(placement)} />
          </div>
        </section>
        <aside className="grid content-start gap-5">
          {pendingPayment && (
            <div className="card border-amber-200 bg-[#fffaf0] p-6">
              <Banknote className="text-amber-800" />
              <h3 className="mt-4 text-xl font-bold">{niceStatus(pendingPayment.fee_type)} fee</h3>
              <p className="mt-2 text-sm text-[var(--muted)]">{money(pendingPayment.amount_cents)} is due before the next stage.</p>
              <button className="btn-primary mt-5 w-full" disabled={Boolean(busy)} onClick={() => onPay(pendingPayment.fee_type)}>
                {busy === `pay-${pendingPayment.fee_type}` ? <LoaderCircle className="animate-spin" size={17} /> : <ShieldCheck size={17} />}
                Pay securely with Paystack
              </button>
            </div>
          )}
          <div className="card p-6">
            <div className="eyebrow">Fees</div>
            <div className="mt-4 grid gap-3">
              {placement.payments.map((payment) => (
                <div className="flex items-center justify-between rounded-2xl border border-[var(--line)] p-4" key={payment.id}>
                  <span><b className="block text-sm">{niceStatus(payment.fee_type)}</b><span className="text-xs text-[var(--muted)]">{money(payment.amount_cents)}</span></span>
                  {payment.status === "paid" ? <CheckCircle2 className="text-[var(--green)]" /> : <span className="pill">{niceStatus(payment.status)}</span>}
                </div>
              ))}
            </div>
          </div>
          {placement.guarantee_until && (
            <div className="card p-6">
              <div className="eyebrow">
                {placement.service_tier === "concierge" ? "Replacement cover" : "Profile rematch"}
              </div>
              <h3 className="mt-2 text-xl font-bold">
                Covered until {new Date(placement.guarantee_until).toLocaleDateString("en-ZA", { dateStyle: "medium" })}
              </h3>
              <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
                Status: {niceStatus(placement.replacement_status || "not_requested")}.
              </p>
              {placement.replacement_status === "not_requested" && (
                <button className="btn-secondary mt-5 w-full" disabled={busy === "replacement"} onClick={onRequestReplacement}>
                  Request {placement.service_tier === "concierge" ? "a replacement" : "a profile rematch"}
                </button>
              )}
            </div>
          )}
          {placement.service_tier === "self_match" && !["placed", "closed", "cancelled"].includes(placement.status) && (
            <div className="card bg-[var(--blue-pale)] p-6">
              <Sparkles className="text-[var(--blue-dark)]" />
              <h3 className="mt-4 text-xl font-bold">Need more help?</h3>
              <p className="mt-2 text-sm leading-6 text-[var(--muted)]">Upgrade without another application fee. Paid candidate access is credited against the Concierge success fee.</p>
              <button className="btn-secondary mt-5 w-full" disabled={busy === "upgrade"} onClick={onUpgrade}>Upgrade to Concierge</button>
            </div>
          )}
        </aside>
      </div>
      <section className="mt-8">
        <div className="flex items-end justify-between gap-4">
          <div><div className="eyebrow">Protected introductions</div><h2 className="display mt-2 text-3xl sm:text-4xl">Your candidate shortlist.</h2></div>
          <span className="pill">{placement.candidates?.length || 0} released</span>
        </div>
        {placement.candidates?.length ? (
          <div className="mt-6 grid gap-5 lg:grid-cols-2">
            {placement.candidates.map((candidate) => (
              <CandidateCard key={candidate.id} candidate={candidate} busy={busy} onAction={onCandidateAction} />
            ))}
          </div>
        ) : (
          <div className="card mt-6 p-10 text-center">
            <Search className="mx-auto text-[var(--blue)]" size={34} />
            <h3 className="mt-4 text-xl font-bold">Profiles are released in stages</h3>
            <p className="mt-2 text-sm text-[var(--muted)]">Each nanny first confirms availability and consent. Only a privacy-safe profile then appears here.</p>
          </div>
        )}
      </section>
    </div>
  );
}

function CandidateCard({ candidate, busy, onAction }: { candidate: Candidate; busy: string; onAction: (id: number, action: "shortlist" | "request-interview") => void }) {
  const checks = Object.values(candidate.verification).filter((value) => value === true).length;
  return (
    <article className="card overflow-hidden">
      <div className="flex items-start gap-4 bg-[var(--blue-pale)] p-5">
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-white text-xl font-bold">{candidate.first_name.slice(0, 1)}</div>
        <div className="flex-1"><h3 className="text-xl font-bold">{candidate.first_name}</h3><div className="mt-1 text-sm text-[var(--muted)]">{candidate.candidate_code} · {candidate.broad_location}</div></div>
      </div>
      <div className="p-5">
        <p className="line-clamp-3 text-sm leading-6 text-[var(--muted)]">{candidate.bio || "Approved My Nanny candidate ready for a long-term opportunity."}</p>
        <div className="mt-4 flex flex-wrap gap-2"><span className="pill">{candidate.experience_count} experience records</span><span className="pill">{checks}/4 checks</span>{candidate.languages.slice(0, 2).map((item) => <span className="pill" key={item}>{item}</span>)}</div>
        <div className="mt-5 flex flex-wrap gap-3 border-t border-[var(--line)] pt-5">
          {candidate.status === "released" && <button className="btn-secondary" disabled={Boolean(busy)} onClick={() => onAction(candidate.id, "shortlist")}><UserRoundCheck size={17} />Shortlist</button>}
          {["released", "shortlisted"].includes(candidate.status) && <button className="btn-primary" disabled={Boolean(busy)} onClick={() => onAction(candidate.id, "request-interview")}><CalendarDays size={17} />Request interview</button>}
          {candidate.interview_scheduled_at && <span className="pill">Interview {new Date(candidate.interview_scheduled_at).toLocaleDateString("en-ZA")}</span>}
        </div>
      </div>
    </article>
  );
}

function OfferCard({ title, subtitle, total, selected, disabled, onSelect, points, concierge = false }: { title: string; subtitle: string; total: number; selected: boolean; disabled: boolean; onSelect: () => void; points: string[]; concierge?: boolean }) {
  return (
    <article className={`card relative overflow-hidden p-7 ${selected ? "ring-2 ring-[var(--blue-dark)]" : ""}`}>
      <div className={`absolute inset-x-0 top-0 h-1.5 ${concierge ? "bg-[var(--coral)]" : "bg-[var(--blue-dark)]"}`} />
      <div className="flex items-start justify-between"><div><div className="eyebrow">{subtitle}</div><h2 className="mt-2 text-3xl font-bold">{title}</h2></div>{concierge ? <Handshake className="text-[var(--coral)]" /> : <Search className="text-[var(--blue-dark)]" />}</div>
      <div className="mt-6 text-sm text-[var(--muted)]">Total if placed</div><div className="mt-1 text-3xl font-bold">{money(total)}</div>
      <ul className="mt-6 grid gap-3">{points.map((point) => <li className="flex gap-3 text-sm" key={point}><Check className="shrink-0 text-[var(--green)]" size={18} />{point}</li>)}</ul>
      <button className="btn-primary mt-7 w-full" disabled={disabled} onClick={onSelect}>{disabled ? "Pilot not open yet" : `Choose ${title}`}</button>
    </article>
  );
}

function PlacementBriefForm({ brief, setBrief, busy, onCancel, onSubmit }: { brief: typeof emptyBrief; setBrief: (value: typeof emptyBrief) => void; busy: boolean; onCancel: () => void; onSubmit: (event: FormEvent) => void }) {
  return (
    <form className="card mt-8 overflow-hidden" onSubmit={onSubmit}>
      <div className="border-b border-[var(--line)] bg-[var(--blue-pale)] p-7"><div className="eyebrow">Family needs assessment</div><h2 className="mt-2 text-3xl font-bold">Tell us about the role.</h2><p className="mt-2 text-[var(--muted)]">Exact household details never appear in a candidate profile.</p></div>
      <div className="grid gap-5 p-7 sm:grid-cols-2">
        <PlacementField label="Role title"><input className="field" required value={brief.role_title} onChange={(event) => setBrief({ ...brief, role_title: event.target.value })} /></PlacementField>
        <PlacementField label="Employment type"><select className="field" value={brief.employment_type} onChange={(event) => setBrief({ ...brief, employment_type: event.target.value })}><option value="full_time">Full-time</option><option value="part_time">Part-time</option><option value="live_in">Live-in</option><option value="live_out">Live-out</option></select></PlacementField>
        <PlacementField label="Start date"><input className="field" type="date" value={brief.start_date} onChange={(event) => setBrief({ ...brief, start_date: event.target.value })} /></PlacementField>
        <PlacementField label="Hours per week"><input className="field" type="number" min="1" max="168" value={brief.hours_per_week} onChange={(event) => setBrief({ ...brief, hours_per_week: event.target.value })} /></PlacementField>
        <PlacementField label="Schedule"><textarea className="field min-h-24" required value={brief.schedule_summary} onChange={(event) => setBrief({ ...brief, schedule_summary: event.target.value })} /></PlacementField>
        <PlacementField label="Duties"><textarea className="field min-h-24" required value={brief.duties} onChange={(event) => setBrief({ ...brief, duties: event.target.value })} /></PlacementField>
        <PlacementField label="Number of children"><input className="field" type="number" min="1" max="12" value={brief.children_count} onChange={(event) => setBrief({ ...brief, children_count: event.target.value })} /></PlacementField>
        <PlacementField label="Children's ages"><input className="field" placeholder="8 months, 4 years" value={brief.children_ages} onChange={(event) => setBrief({ ...brief, children_ages: event.target.value })} /></PlacementField>
        <PlacementField label="Monthly salary from"><input className="field" type="number" min="1" required value={brief.salary_min} onChange={(event) => setBrief({ ...brief, salary_min: event.target.value })} /></PlacementField>
        <PlacementField label="Monthly salary to"><input className="field" type="number" min="1" required value={brief.salary_max} onChange={(event) => setBrief({ ...brief, salary_max: event.target.value })} /></PlacementField>
        <PlacementField label="Suburb"><input className="field" required value={brief.location_suburb} onChange={(event) => setBrief({ ...brief, location_suburb: event.target.value })} /></PlacementField>
        <PlacementField label="City"><input className="field" required value={brief.location_city} onChange={(event) => setBrief({ ...brief, location_city: event.target.value })} /></PlacementField>
        <PlacementField label="Province"><input className="field" value={brief.location_province} onChange={(event) => setBrief({ ...brief, location_province: event.target.value })} /></PlacementField>
        <PlacementField label="Preferred languages"><input className="field" placeholder="English, isiZulu" value={brief.languages} onChange={(event) => setBrief({ ...brief, languages: event.target.value })} /></PlacementField>
        <PlacementField label="Special requirements"><textarea className="field min-h-20" value={brief.special_requirements} onChange={(event) => setBrief({ ...brief, special_requirements: event.target.value })} /></PlacementField>
        <PlacementField label="Pets or household notes"><textarea className="field min-h-20" value={brief.pets} onChange={(event) => setBrief({ ...brief, pets: event.target.value })} /></PlacementField>
        <div className="sm:col-span-2 flex flex-wrap gap-5 rounded-2xl border border-[var(--line)] p-5">{(["live_in", "drivers_license_required", "own_car_required"] as const).map((key) => <label className="flex items-center gap-2 text-sm font-bold" key={key}><input type="checkbox" checked={brief[key]} onChange={(event) => setBrief({ ...brief, [key]: event.target.checked })} />{niceStatus(key)}</label>)}</div>
        <div className="sm:col-span-2 flex justify-end gap-3 border-t border-[var(--line)] pt-6"><button type="button" className="btn-quiet" onClick={onCancel}>Cancel</button><button className="btn-primary" disabled={busy}>{busy ? <LoaderCircle className="animate-spin" size={17} /> : <ArrowRight size={17} />}Save family brief</button></div>
      </div>
    </form>
  );
}

function splitList(value: string) {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

function requirements(placement: Placement) {
  return [
    placement.live_in && "Live-in",
    placement.drivers_license_required && "Driver's licence",
    placement.own_car_required && "Own car",
    placement.special_requirements,
  ].filter(Boolean).join(" · ") || "No additional requirements";
}
