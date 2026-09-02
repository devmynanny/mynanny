"use client";

import { apiJson, apiMediaUrl } from "@/lib/api";
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
import { Dispatch, FormEvent, SetStateAction, useEffect, useState } from "react";
import {
  PlacementField,
  PlacementHeading,
  PlacementInfo,
  PlacementNotice,
} from "./shared";
import { InterviewCommunication } from "./communication";
import { Candidate, Config, dateTime, money, niceStatus, Placement } from "./types";

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

const weekdayNames = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export function ParentPermanentPlacements() {
  const [config, setConfig] = useState<Config | null>(null);
  const [placements, setPlacements] = useState<Placement[]>([]);
  const [selected, setSelected] = useState<Placement | null>(null);
  const [tier, setTier] = useState<"self_match" | "concierge" | null>(null);
  const [brief, setBrief] = useState(emptyBrief);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  const [interviewFeedback, setInterviewFeedback] = useState<Record<number, string>>({});

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

  async function recordInterviewDecision(candidateId: number, decision: "reject" | "maybe" | "trial" | "offer" | "admin_support") {
    if (!selected) return;
    const feedback = (interviewFeedback[candidateId] || "").trim();
    if (feedback.length < 3) {
      setMessage("Add a short interview note before choosing the next step.");
      return;
    }
    setBusy(`decision-${candidateId}`);
    try {
      setSelected(await apiJson<Placement>(`/parents/me/permanent-placements/${selected.id}/candidates/${candidateId}/interview-decision`, {
        method: "POST",
        body: JSON.stringify({ decision, feedback }),
      }));
      setMessage(decision === "maybe" ? "Candidate added to Maybe for four days." : "Interview feedback and next step saved.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to save interview feedback.");
    } finally {
      setBusy("");
    }
  }

  async function requestTrial(candidateId: number, startsAt: string, endsAt: string, note: string) {
    if (!selected) return;
    setBusy(`trial-${candidateId}`);
    try {
      setSelected(await apiJson<Placement>(`/parents/me/permanent-placements/${selected.id}/candidates/${candidateId}/trial`, {
        method: "POST",
        body: JSON.stringify({ starts_at: startsAt, ends_at: endsAt, note: note || null }),
      }));
      setMessage("Paid trial request sent. The nanny can accept, decline or suggest another time.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to send the trial request.");
    } finally {
      setBusy("");
    }
  }

  async function sendOffer(candidateId: number, offer: {
    salary: string;
    startDate: string;
    workingDays: number[];
    startTime: string;
    endTime: string;
    terms: string;
  }) {
    if (!selected) return;
    setBusy(`offer-${candidateId}`);
    try {
      setSelected(await apiJson<Placement>(`/parents/me/permanent-placements/${selected.id}/candidates/${candidateId}/offer`, {
        method: "POST",
        body: JSON.stringify({
          salary_cents: Math.round(Number(offer.salary) * 100),
          start_date: offer.startDate,
          working_days: offer.workingDays,
          start_time: offer.startTime,
          end_time: offer.endTime,
          terms: offer.terms,
        }),
      }));
      setMessage("Formal offer sent. My Nanny remains available to support questions and salary discussions.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to send the offer.");
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
      "Please explain why you need a replacement.",
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
        interviewFeedback={interviewFeedback}
        setInterviewFeedback={setInterviewFeedback}
        onInterviewDecision={recordInterviewDecision}
        onRequestTrial={requestTrial}
        onSendOffer={sendOffer}
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
            `${money(config.pricing.self_match.candidate_access_fee_cents)} top-up for the ${money(config.pricing.self_match.interview_package_fee_cents)} interview package`,
            `${config.pricing.self_match.profile_limit} profiles and ${config.pricing.self_match.interview_limit} interviews`,
            `One replacement within ${config.pricing.self_match.replacement_days} days`,
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
            `${money(config.pricing.concierge.consultation_fee_cents)} consultation`,
            `${money(config.pricing.concierge.engagement_fee_cents)} engagement and ${money(config.pricing.concierge.success_balance_cents)} placement balance`,
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
  interviewFeedback,
  setInterviewFeedback,
  onInterviewDecision,
  onRequestTrial,
  onSendOffer,
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
  interviewFeedback: Record<number, string>;
  setInterviewFeedback: (value: Record<number, string>) => void;
  onInterviewDecision: (id: number, decision: "reject" | "maybe" | "trial" | "offer" | "admin_support") => void;
  onRequestTrial: (id: number, startsAt: string, endsAt: string, note: string) => void;
  onSendOffer: (id: number, offer: { salary: string; startDate: string; workingDays: number[]; startTime: string; endTime: string; terms: string }) => void;
}) {
  const dueFeeType =
    placement.status === "awaiting_initial_payment"
      ? placement.service_tier === "self_match"
        ? "activation"
        : "application"
      : placement.status === "awaiting_candidate_access"
        ? "candidate_access"
        : placement.status === "awaiting_engagement_payment"
          ? "engagement"
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
          body={`${niceStatus(placement.service_tier)} placement in ${placement.location_suburb}. Track every managed introduction, interview and payment here.`}
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
            <div className="eyebrow">Interview credits</div>
            <div className="mt-2 text-3xl font-bold">{placement.interview_credits.available} available</div>
            <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
              {placement.interview_credits.used} of {placement.interview_credits.included} accepted interview credits used. Invitations do not use a credit until a nanny accepts.
            </p>
          </div>
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
            {placement.invoices.length > 0 && <div className="mt-5 border-t border-[var(--line)] pt-5"><div className="text-sm font-bold">Invoices and receipts</div><div className="mt-3 grid gap-2">{placement.invoices.map((invoice) => <div className="rounded-xl bg-[var(--blue-pale)] p-3 text-sm" key={invoice.id}><div className="flex items-center justify-between gap-3"><span><b>{invoice.invoice_number || "Invoice draft"}</b><span className="ml-2 text-[var(--muted)]">{money(invoice.total_cents)}</span></span><span className="pill">{niceStatus(invoice.status)}</span></div><div className="mt-2 flex flex-wrap gap-3">{invoice.invoice_pdf_url && <a className="font-bold underline" href={apiMediaUrl(invoice.invoice_pdf_url)} target="_blank" rel="noreferrer">Download invoice</a>}{invoice.receipt_pdf_url && <a className="font-bold underline" href={apiMediaUrl(invoice.receipt_pdf_url)} target="_blank" rel="noreferrer">Download receipt</a>}{!invoice.invoice_pdf_url && <span className="text-[var(--muted)]">Awaiting billing setup or issue</span>}</div></div>)}</div></div>}
          </div>
          {placement.guarantee_until && (
            <div className="card p-6">
              <div className="eyebrow">
                Replacement cover
              </div>
              <h3 className="mt-2 text-xl font-bold">
                Covered until {new Date(placement.guarantee_until).toLocaleDateString("en-ZA", { dateStyle: "medium" })}
              </h3>
              <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
                Status: {niceStatus(placement.replacement_status || "not_requested")}.
              </p>
              {placement.replacement_status === "not_requested" && (
                <button className="btn-secondary mt-5 w-full" disabled={busy === "replacement"} onClick={onRequestReplacement}>
                  Request a replacement
                </button>
              )}
            </div>
          )}
          {placement.service_tier === "self_match" && !["placed", "closed", "cancelled"].includes(placement.status) && (
            <div className="card bg-[var(--blue-pale)] p-6">
              <Sparkles className="text-[var(--blue-dark)]" />
              <h3 className="mt-4 text-xl font-bold">Need more help?</h3>
              <p className="mt-2 text-sm leading-6 text-[var(--muted)]">Upgrade without another application fee. Your paid interview package is credited against the remaining Concierge placement service.</p>
              <button className="btn-secondary mt-5 w-full" disabled={busy === "upgrade"} onClick={onUpgrade}>Upgrade to Concierge</button>
            </div>
          )}
        </aside>
      </div>
      <section className="mt-8">
        <div className="flex items-end justify-between gap-4">
          <div><div className="eyebrow">Managed introductions</div><h2 className="display mt-2 text-3xl sm:text-4xl">Your candidate shortlist.</h2></div>
          <span className="pill">{placement.candidates?.length || 0} released</span>
        </div>
        {placement.candidates?.length ? (
          <div className="mt-6 grid gap-5 lg:grid-cols-2">
            {placement.candidates.map((candidate) => (
              <CandidateCard key={candidate.id} candidate={candidate} busy={busy} onAction={onCandidateAction} feedback={interviewFeedback[candidate.id] || candidate.parent_interview_feedback || ""} onFeedback={(value) => setInterviewFeedback({ ...interviewFeedback, [candidate.id]: value })} onDecision={onInterviewDecision} onRequestTrial={onRequestTrial} onSendOffer={onSendOffer} />
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

function CandidateCard({
  candidate,
  busy,
  onAction,
  feedback,
  onFeedback,
  onDecision,
  onRequestTrial,
  onSendOffer,
}: {
  candidate: Candidate;
  busy: string;
  onAction: (id: number, action: "shortlist" | "request-interview") => void;
  feedback: string;
  onFeedback: (value: string) => void;
  onDecision: (id: number, decision: "reject" | "maybe" | "trial" | "offer" | "admin_support") => void;
  onRequestTrial: (id: number, startsAt: string, endsAt: string, note: string) => void;
  onSendOffer: (id: number, offer: { salary: string; startDate: string; workingDays: number[]; startTime: string; endTime: string; terms: string }) => void;
}) {
  const checks = Object.values(candidate.verification).filter((value) => value === true).length;
  const [trialStart, setTrialStart] = useState("");
  const [trialEnd, setTrialEnd] = useState("");
  const [trialNote, setTrialNote] = useState("");
  const [offer, setOffer] = useState({
    salary: candidate.desired_salary_min_cents ? String(candidate.desired_salary_min_cents / 100) : "",
    startDate: "",
    workingDays: [0, 1, 2, 3, 4],
    startTime: "07:00",
    endTime: "17:00",
    terms: "Permanent nanny position subject to the agreed duties and My Nanny placement terms.",
  });
  const trialReady = Boolean(trialStart && trialEnd);
  const offerReady = Boolean(offer.salary && offer.startDate && offer.workingDays.length && offer.startTime && offer.endTime && offer.terms.trim().length >= 5);

  function toggleWorkingDay(day: number) {
    setOffer({
      ...offer,
      workingDays: offer.workingDays.includes(day)
        ? offer.workingDays.filter((value) => value !== day)
        : [...offer.workingDays, day].sort(),
    });
  }

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
          {candidate.interview_invite_status === "pending" && <span className="pill">Awaiting nanny response</span>}
          {candidate.interview_invite_status === "accepted" && !candidate.interview_scheduled_at && <span className="pill">Interview accepted</span>}
          {["declined", "cancelled_by_nanny", "not_held"].includes(candidate.interview_invite_status) && <span className="pill">Credit not used</span>}
          {candidate.interview_scheduled_at && <span className="pill">Interview {new Date(candidate.interview_scheduled_at).toLocaleDateString("en-ZA")}</span>}
        </div>
        {candidate.interview_completed_at && !["reject", "trial", "offer"].includes(candidate.parent_interview_decision || "") && (
          <div className="mt-5 rounded-2xl bg-[var(--blue-pale)] p-5">
            <b>Interview feedback and next step</b>
            <textarea className="field mt-3 min-h-24 bg-white" value={feedback} onChange={(event) => onFeedback(event.target.value)} placeholder="How did you experience the interview?"/>
            <div className="mt-4 flex flex-wrap gap-2">
              <button className="btn-quiet !min-h-9 text-red-700" disabled={Boolean(busy)} onClick={() => onDecision(candidate.id, "reject")}>Reject</button>
              <button className="btn-secondary !min-h-9" disabled={Boolean(busy)} onClick={() => onDecision(candidate.id, "maybe")}>Maybe</button>
              <button className="btn-secondary !min-h-9" disabled={Boolean(busy)} onClick={() => onDecision(candidate.id, "trial")}>Request trial</button>
              <button className="btn-primary !min-h-9" disabled={Boolean(busy)} onClick={() => onDecision(candidate.id, "offer")}>Make an offer</button>
              <button className="btn-quiet !min-h-9" disabled={Boolean(busy)} onClick={() => onDecision(candidate.id, "admin_support")}>Ask My Nanny</button>
            </div>
            {candidate.maybe_until && <p className="mt-3 text-xs font-semibold text-[var(--muted)]">Maybe decision due by {new Date(candidate.maybe_until).toLocaleString("en-ZA")}</p>}
          </div>
        )}
        {["accepted", "completed"].includes(candidate.interview_invite_status) && <InterviewCommunication candidateId={candidate.id} />}
        {candidate.parent_interview_decision === "trial" && (
          <div className="mt-5 rounded-2xl border border-[var(--line)] p-5">
            <div className="flex flex-wrap items-center justify-between gap-2"><b>Paid trial</b><span className="pill">{niceStatus(candidate.trial_status || "choose dates")}</span></div>
            {candidate.trial_alternative_at && <p className="mt-3 rounded-xl bg-[var(--blue-pale)] p-3 text-sm"><b>Alternative suggested:</b> {dateTime(candidate.trial_alternative_at)}</p>}
            {candidate.trial_status === "pending" || candidate.trial_status === "accepted" ? (
              <div className="mt-3 text-sm leading-6 text-[var(--muted)]">
                {dateTime(candidate.trial_scheduled_at)} to {dateTime(candidate.trial_ends_at)} · {candidate.trial_status === "pending" ? "Awaiting the nanny's response" : "Accepted by the nanny"}
              </div>
            ) : (
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <PlacementField label="Trial starts"><input className="field" type="datetime-local" value={trialStart} onChange={(event) => setTrialStart(event.target.value)} /></PlacementField>
                <PlacementField label="Trial ends"><input className="field" type="datetime-local" value={trialEnd} onChange={(event) => setTrialEnd(event.target.value)} /></PlacementField>
                <div className="sm:col-span-2"><textarea className="field min-h-20" value={trialNote} onChange={(event) => setTrialNote(event.target.value)} placeholder="Transport, meeting point or trial notes" /></div>
                <button className="btn-primary sm:col-span-2" disabled={Boolean(busy) || !trialReady} onClick={() => onRequestTrial(candidate.id, trialStart, trialEnd, trialNote)}><CalendarDays size={17} />Send trial request</button>
              </div>
            )}
          </div>
        )}
        {candidate.parent_interview_decision === "offer" && (
          <div className="mt-5 rounded-2xl border border-[var(--line)] p-5">
            <div className="flex flex-wrap items-center justify-between gap-2"><b>Permanent offer</b><span className="pill">{niceStatus(candidate.offer_status || "prepare offer")}</span></div>
            {candidate.offer_status === "pending" || candidate.offer_status === "accepted" ? (
              <div className="mt-3 grid gap-2 text-sm text-[var(--muted)]">
                <span><b>Salary:</b> {money(candidate.offer_salary_cents)} monthly</span>
                <span><b>Starts:</b> {candidate.offer_start_date || "To confirm"}</span>
                <span><b>Working schedule:</b> {(candidate.offer_working_days || []).map((day) => weekdayNames[day]).join(", ")} · {candidate.offer_start_time}-{candidate.offer_end_time}</span>
                <span>{candidate.offer_status === "pending" ? "Awaiting the nanny's response." : "Offer accepted. The agreed working days are now blocked from her short-term calendar."}</span>
              </div>
            ) : (
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <PlacementField label="Monthly salary"><input className="field" type="number" min="1" value={offer.salary} onChange={(event) => setOffer({ ...offer, salary: event.target.value })} /></PlacementField>
                <PlacementField label="Start date"><input className="field" type="date" value={offer.startDate} onChange={(event) => setOffer({ ...offer, startDate: event.target.value })} /></PlacementField>
                <PlacementField label="Working from"><input className="field" type="time" value={offer.startTime} onChange={(event) => setOffer({ ...offer, startTime: event.target.value })} /></PlacementField>
                <PlacementField label="Working until"><input className="field" type="time" value={offer.endTime} onChange={(event) => setOffer({ ...offer, endTime: event.target.value })} /></PlacementField>
                <div className="sm:col-span-2"><div className="mb-2 text-sm font-bold">Working days</div><div className="flex flex-wrap gap-2">{weekdayNames.map((name, day) => <button type="button" key={name} className={offer.workingDays.includes(day) ? "btn-primary !min-h-9" : "btn-secondary !min-h-9"} onClick={() => toggleWorkingDay(day)}>{name.slice(0, 3)}</button>)}</div></div>
                <div className="sm:col-span-2"><textarea className="field min-h-24" value={offer.terms} onChange={(event) => setOffer({ ...offer, terms: event.target.value })} placeholder="Role, duties and any agreed terms" /></div>
                <button className="btn-primary sm:col-span-2" disabled={Boolean(busy) || !offerReady} onClick={() => onSendOffer(candidate.id, offer)}><Handshake size={17} />Send formal offer</button>
              </div>
            )}
          </div>
        )}
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

function PlacementBriefForm({ brief, setBrief, busy, onCancel, onSubmit }: { brief: typeof emptyBrief; setBrief: Dispatch<SetStateAction<typeof emptyBrief>>; busy: boolean; onCancel: () => void; onSubmit: (event: FormEvent) => void }) {
  return (
    <form className="card mt-8 overflow-hidden" onSubmit={onSubmit}>
      <div className="border-b border-[var(--line)] bg-[var(--blue-pale)] p-7"><div className="eyebrow">Family needs assessment</div><h2 className="mt-2 text-3xl font-bold">Tell us about the role.</h2><p className="mt-2 text-[var(--muted)]">Exact household details never appear in a candidate profile.</p></div>
      <div className="grid gap-5 p-7 sm:grid-cols-2">
        <PlacementField label="Role title"><input className="field" required value={brief.role_title} onChange={(event) => setBrief((current) => ({ ...current, role_title: event.target.value }))} /></PlacementField>
        <PlacementField label="Employment type"><select className="field" value={brief.employment_type} onChange={(event) => setBrief((current) => ({ ...current, employment_type: event.target.value }))}><option value="full_time">Full-time</option><option value="part_time">Part-time</option><option value="live_in">Live-in</option><option value="live_out">Live-out</option></select></PlacementField>
        <PlacementField label="Start date"><input className="field" type="date" value={brief.start_date} onChange={(event) => setBrief((current) => ({ ...current, start_date: event.target.value }))} /></PlacementField>
        <PlacementField label="Hours per week"><input className="field" type="number" min="1" max="168" value={brief.hours_per_week} onChange={(event) => setBrief((current) => ({ ...current, hours_per_week: event.target.value }))} /></PlacementField>
        <PlacementField label="Schedule"><textarea className="field min-h-24" required value={brief.schedule_summary} onChange={(event) => setBrief((current) => ({ ...current, schedule_summary: event.target.value }))} /></PlacementField>
        <PlacementField label="Duties"><textarea className="field min-h-24" required value={brief.duties} onChange={(event) => setBrief((current) => ({ ...current, duties: event.target.value }))} /></PlacementField>
        <PlacementField label="Number of children"><input className="field" type="number" min="1" max="12" value={brief.children_count} onChange={(event) => setBrief((current) => ({ ...current, children_count: event.target.value }))} /></PlacementField>
        <PlacementField label="Children's ages"><input className="field" placeholder="8 months, 4 years" value={brief.children_ages} onChange={(event) => setBrief((current) => ({ ...current, children_ages: event.target.value }))} /></PlacementField>
        <PlacementField label="Monthly salary from"><input className="field" type="number" min="1" required value={brief.salary_min} onChange={(event) => setBrief((current) => ({ ...current, salary_min: event.target.value }))} /></PlacementField>
        <PlacementField label="Monthly salary to"><input className="field" type="number" min="1" required value={brief.salary_max} onChange={(event) => setBrief((current) => ({ ...current, salary_max: event.target.value }))} /></PlacementField>
        <PlacementField label="Suburb"><input className="field" required value={brief.location_suburb} onChange={(event) => setBrief((current) => ({ ...current, location_suburb: event.target.value }))} /></PlacementField>
        <PlacementField label="City"><input className="field" required value={brief.location_city} onChange={(event) => setBrief((current) => ({ ...current, location_city: event.target.value }))} /></PlacementField>
        <PlacementField label="Province"><input className="field" value={brief.location_province} onChange={(event) => setBrief((current) => ({ ...current, location_province: event.target.value }))} /></PlacementField>
        <PlacementField label="Preferred languages"><input className="field" placeholder="English, isiZulu" value={brief.languages} onChange={(event) => setBrief((current) => ({ ...current, languages: event.target.value }))} /></PlacementField>
        <PlacementField label="Special requirements"><textarea className="field min-h-20" value={brief.special_requirements} onChange={(event) => setBrief((current) => ({ ...current, special_requirements: event.target.value }))} /></PlacementField>
        <PlacementField label="Pets or household notes"><textarea className="field min-h-20" value={brief.pets} onChange={(event) => setBrief((current) => ({ ...current, pets: event.target.value }))} /></PlacementField>
        <div className="sm:col-span-2 flex flex-wrap gap-5 rounded-2xl border border-[var(--line)] p-5">{(["live_in", "drivers_license_required", "own_car_required"] as const).map((key) => <label className="flex items-center gap-2 text-sm font-bold" key={key}><input type="checkbox" checked={brief[key]} onChange={(event) => setBrief((current) => ({ ...current, [key]: event.target.checked }))} />{niceStatus(key)}</label>)}</div>
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
