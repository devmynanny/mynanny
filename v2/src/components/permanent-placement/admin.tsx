"use client";

import { apiJson } from "@/lib/api";
import {
  BadgeCheck,
  Banknote,
  BriefcaseBusiness,
  CheckCircle2,
  ChevronRight,
  Handshake,
  LoaderCircle,
  Search,
  ShieldCheck,
  UsersRound,
} from "lucide-react";
import { ReactNode, useEffect, useState } from "react";
import {
  PlacementHeading,
  PlacementInfo,
  PlacementNotice,
} from "./shared";
import { Candidate, money, niceStatus, Placement, Pricing } from "./types";

type AdminOverview = {
  enabled: boolean;
  pricing: Pricing;
  metrics: {
    total: number;
    active: number;
    awaiting_payment: number;
    interviewing: number;
    placed: number;
    revenue_cents: number;
  };
  results: Placement[];
};

type EligibleNanny = {
  nanny_id: number;
  name: string;
  location: string;
  desired_salary_min_cents?: number | null;
  desired_salary_max_cents?: number | null;
};

export function AdminPermanentPlacements() {
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [detail, setDetail] = useState<Placement | null>(null);
  const [eligible, setEligible] = useState<EligibleNanny[]>([]);
  const [inviteNanny, setInviteNanny] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState("");

  async function load(selectId?: number) {
    const [next, nannies] = await Promise.all([
      apiJson<AdminOverview>("/admin/permanent-placements/overview"),
      apiJson<{ results: EligibleNanny[] }>(
        "/admin/permanent-placements/eligible-nannies",
      ),
    ]);
    setOverview(next);
    setEligible(nannies.results || []);
    const id = selectId || detail?.id;
    if (id) {
      setDetail(
        await apiJson<Placement>(`/admin/permanent-placements/${id}`),
      );
    }
  }

  useEffect(() => {
    Promise.all([
      apiJson<AdminOverview>("/admin/permanent-placements/overview"),
      apiJson<{ results: EligibleNanny[] }>(
        "/admin/permanent-placements/eligible-nannies",
      ),
    ])
      .then(([next, nannies]) => {
        setOverview(next);
        setEligible(nannies.results || []);
      })
      .catch((error) =>
        setMessage(
          error instanceof Error
            ? error.message
            : "Unable to load the placement pipeline.",
        ),
      );
  }, []);

  async function run(
    label: string,
    path: string,
    body: Record<string, unknown> = {},
  ) {
    setBusy(label);
    try {
      await apiJson(path, { method: "POST", body: JSON.stringify(body) });
      setMessage("Placement updated successfully.");
      await load(detail?.id);
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Unable to update placement.",
      );
    } finally {
      setBusy("");
    }
  }

  async function togglePilot() {
    if (!overview) return;
    setBusy("toggle");
    try {
      await apiJson("/admin/permanent-placements/settings", {
        method: "PUT",
        body: JSON.stringify({ enabled: !overview.enabled }),
      });
      setMessage(
        !overview.enabled
          ? "The permanent-placement pilot is open to new family briefs."
          : "The pilot is closed to new briefs. Existing searches remain available.",
      );
      await load();
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Unable to update pilot access.",
      );
    } finally {
      setBusy("");
    }
  }

  if (!overview)
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <LoaderCircle className="animate-spin" />
      </div>
    );

  if (detail)
    return (
      <PlacementDetail
        placement={detail}
        eligible={eligible}
        inviteNanny={inviteNanny}
        setInviteNanny={setInviteNanny}
        message={message}
        busy={busy}
        run={run}
        onBack={() => setDetail(null)}
      />
    );

  return (
    <div className="mx-auto max-w-7xl">
      <div className="flex flex-wrap items-start justify-between gap-5">
        <PlacementHeading
          eyebrow="Placement operations"
          title="Permanent placements."
          body="Qualify family briefs, protect candidate consent, coordinate introductions and track placement revenue in one operational pipeline."
        />
        <button
          className={overview.enabled ? "btn-secondary" : "btn-primary"}
          disabled={busy === "toggle"}
          onClick={() => void togglePilot()}
        >
          {overview.enabled ? (
            <><CheckCircle2 className="text-[var(--green)]" />Pilot open</>
          ) : (
            <><ShieldCheck />Open pilot</>
          )}
        </button>
      </div>
      <PlacementNotice message={message} />
      <div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <Metric label="All searches" value={String(overview.metrics.total)} icon={<BriefcaseBusiness />} />
        <Metric label="Active" value={String(overview.metrics.active)} icon={<Search />} />
        <Metric label="Awaiting payment" value={String(overview.metrics.awaiting_payment)} icon={<Banknote />} />
        <Metric label="Interviewing" value={String(overview.metrics.interviewing)} icon={<UsersRound />} />
        <Metric label="Revenue" value={money(overview.metrics.revenue_cents)} icon={<Handshake />} />
      </div>
      <section className="mt-8">
        <div className="flex items-center justify-between"><div><div className="eyebrow">Live pipeline</div><h2 className="mt-2 text-3xl font-bold">Family searches</h2></div><span className="pill">Pilot {overview.enabled ? "open" : "closed"}</span></div>
        {overview.results.length ? (
          <div className="card mt-5 overflow-hidden">
            <div className="hidden grid-cols-[80px_1.2fr_.75fr_.75fr_160px_30px] gap-4 border-b border-[var(--line)] bg-[var(--blue-pale)] px-6 py-4 text-xs font-extrabold uppercase tracking-wider text-[var(--muted)] lg:grid"><span>Ref</span><span>Family and role</span><span>Service</span><span>Location</span><span>Status</span><span /></div>
            {overview.results.map((row) => (
              <button key={row.id} onClick={() => void load(row.id)} className="grid w-full items-center gap-3 border-b border-[var(--line)] px-6 py-5 text-left last:border-0 hover:bg-[var(--blue-pale)] lg:grid-cols-[80px_1.2fr_.75fr_.75fr_160px_30px] lg:gap-4">
                <b>#{row.id}</b><span><b className="block">{row.parent_name || "Family"}</b><span className="text-sm text-[var(--muted)]">{row.role_title}</span></span><span className="text-sm">{niceStatus(row.service_tier)}</span><span className="text-sm">{row.location_suburb}</span><span className="pill w-fit">{niceStatus(row.status)}</span><ChevronRight />
              </button>
            ))}
          </div>
        ) : (
          <div className="card mt-5 p-12 text-center"><Handshake className="mx-auto text-[var(--blue)]" size={38} /><h3 className="mt-4 text-xl font-bold">No permanent placement briefs yet</h3><p className="mt-2 text-[var(--muted)]">Open the pilot when the team is ready to receive the first family application.</p></div>
        )}
      </section>
    </div>
  );
}

function PlacementDetail({
  placement,
  eligible,
  inviteNanny,
  setInviteNanny,
  message,
  busy,
  run,
  onBack,
}: {
  placement: Placement;
  eligible: EligibleNanny[];
  inviteNanny: string;
  setInviteNanny: (value: string) => void;
  message: string;
  busy: string;
  run: (label: string, path: string, body?: Record<string, unknown>) => Promise<void>;
  onBack: () => void;
}) {
  return (
    <div className="mx-auto max-w-7xl">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <PlacementHeading
          eyebrow={`Placement #${placement.id}`}
          title={placement.role_title}
          body={`${placement.parent_name || "Family"} · ${niceStatus(placement.service_tier)} · ${placement.location_suburb}, ${placement.location_city}`}
        />
        <button className="btn-secondary" onClick={onBack}>Back to pipeline</button>
      </div>
      <PlacementNotice message={message} />
      <div className="mt-8 grid gap-6 xl:grid-cols-[1fr_.72fr]">
        <div className="grid content-start gap-6">
          <section className="card p-6 sm:p-8">
            <div className="flex justify-between gap-3"><h2 className="text-2xl font-bold">Family brief</h2><span className="pill">{niceStatus(placement.status)}</span></div>
            <div className="mt-6 grid gap-5 sm:grid-cols-2">
              <PlacementInfo label="Family" value={`${placement.parent_name || "-"}\n${placement.parent_email || ""}\n${placement.parent_phone || ""}`} />
              <PlacementInfo label="Salary" value={`${money(placement.salary_min_cents)} - ${money(placement.salary_max_cents)} monthly`} />
              <PlacementInfo label="Schedule" value={placement.schedule_summary} />
              <PlacementInfo label="Duties" value={placement.duties} />
              <PlacementInfo label="Location" value={`${placement.location_suburb}, ${placement.location_city}`} />
              <PlacementInfo label="Requirements" value={requirements(placement)} />
            </div>
          </section>
          <section>
            <div className="flex items-center justify-between"><div><div className="eyebrow">Candidate pipeline</div><h2 className="mt-2 text-3xl font-bold">Protected introductions</h2></div><span className="pill">{placement.candidates?.length || 0}</span></div>
            <div className="card mt-5 p-5">
              <div className="flex flex-col gap-3 sm:flex-row">
                <select className="field" value={inviteNanny} onChange={(event) => setInviteNanny(event.target.value)}>
                  <option value="">Choose an opted-in nanny</option>
                  {eligible.map((nanny) => <option key={nanny.nanny_id} value={nanny.nanny_id}>{nanny.name} · {nanny.location} · {money(nanny.desired_salary_min_cents)}-{money(nanny.desired_salary_max_cents)}</option>)}
                </select>
                <button className="btn-primary shrink-0" disabled={!inviteNanny || Boolean(busy)} onClick={() => void run("invite", `/admin/permanent-placements/${placement.id}/candidates`, { nanny_id: Number(inviteNanny), note: null })}><UsersRound size={17} />Invite candidate</button>
              </div>
            </div>
            {placement.candidates?.length ? (
              <div className="mt-4 grid gap-4">
                {placement.candidates.map((candidate) => <AdminCandidateCard key={candidate.id} placement={placement} candidate={candidate} busy={busy} run={run} />)}
              </div>
            ) : <div className="card mt-4 p-8 text-center text-[var(--muted)]">Invite an opted-in nanny to begin the consent process.</div>}
          </section>
        </div>
        <aside className="grid content-start gap-5">
          <div className="card p-6"><div className="eyebrow">Next action</div><h3 className="mt-2 text-xl font-bold">{nextAction(placement.status)}</h3><div className="mt-5 grid gap-3">
            {placement.status === "brief_submitted" && <button className="btn-primary" disabled={Boolean(busy)} onClick={() => void run("qualify", `/admin/permanent-placements/${placement.id}/qualify`, { note: "Family brief qualified" })}><CheckCircle2 size={17} />Qualify family brief</button>}
            {["awaiting_initial_payment", "awaiting_candidate_access", "awaiting_success_fee"].includes(placement.status) && <button className="btn-secondary" disabled={Boolean(busy)} onClick={() => recordPayment(placement, run)}>Record offline/test payment</button>}
            {placement.replacement_status === "requested" && <><button className="btn-primary" disabled={Boolean(busy)} onClick={() => void run("replacement-approved", `/admin/permanent-placements/${placement.id}/replacement`, { decision: "approved", note: "Replacement search approved within the cover period" })}>Approve replacement search</button><button className="btn-quiet text-red-700" disabled={Boolean(busy)} onClick={() => void run("replacement-declined", `/admin/permanent-placements/${placement.id}/replacement`, { decision: "declined", note: "Replacement request reviewed and declined" })}>Decline request</button></>}
          </div></div>
          <div className="card p-6"><div className="eyebrow">Fees</div><div className="mt-4 grid gap-3">{placement.payments.map((payment) => <div className="flex items-center justify-between rounded-2xl border border-[var(--line)] p-4" key={payment.id}><span><b className="block text-sm">{niceStatus(payment.fee_type)}</b><span className="text-xs text-[var(--muted)]">{money(payment.amount_cents)}</span></span>{payment.status === "paid" ? <BadgeCheck className="text-[var(--green)]" /> : <span className="pill">{niceStatus(payment.status)}</span>}</div>)}</div></div>
          <div className="card p-6"><div className="eyebrow">Commercial protection</div><ul className="mt-4 grid gap-3 text-sm leading-6 text-[var(--muted)]"><li>Candidate contact details remain private until approved introduction.</li><li>Introductions are protected for 12 months.</li><li>Trial days and reasonable transport are paid directly to the nanny.</li><li>{placement.service_tier === "concierge" ? "One replacement is included for 90 days." : "A 30-day profile rematch is included."}</li></ul></div>
        </aside>
      </div>
    </div>
  );
}

function AdminCandidateCard({ placement, candidate, busy, run }: { placement: Placement; candidate: Candidate; busy: string; run: (label: string, path: string, body?: Record<string, unknown>) => Promise<void> }) {
  return (
    <article className="card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="text-lg font-bold">{candidate.full_name || candidate.first_name} <span className="ml-2 text-xs text-[var(--muted)]">{candidate.candidate_code}</span></h3><div className="mt-1 text-sm text-[var(--muted)]">{candidate.phone || "No phone"} · {candidate.broad_location}</div></div><div className="flex gap-2"><span className="pill">{niceStatus(candidate.consent_status)}</span><span className="pill">{niceStatus(candidate.status)}</span></div></div>
      <div className="mt-4 flex flex-wrap gap-2">
        {candidate.consent_status === "accepted" && !candidate.profile_released_at && <button className="btn-secondary !min-h-9" disabled={Boolean(busy)} onClick={() => void run("release", `/admin/permanent-placements/${placement.id}/candidates/${candidate.id}/release`)}>Release profile</button>}
        {candidate.status === "interview_requested" && <button className="btn-primary !min-h-9" disabled={Boolean(busy)} onClick={() => scheduleInterview(placement.id, candidate.id, run)}>Schedule interview</button>}
        {["interview_scheduled", "interviewed"].includes(candidate.status) && <button className="btn-secondary !min-h-9" disabled={Boolean(busy)} onClick={() => recordTrial(placement.id, candidate.id, run)}>Record paid trial</button>}
        {["interviewed", "trial", "offered"].includes(candidate.status) && <button className="btn-primary !min-h-9" disabled={Boolean(busy)} onClick={() => void run("hire", `/admin/permanent-placements/${placement.id}/candidates/${candidate.id}/hire`, { note: "Placement confirmed by Admin" })}>Mark hired</button>}
      </div>
      {candidate.interview_scheduled_at && <div className="mt-3 text-sm text-[var(--muted)]">Interview: {new Date(candidate.interview_scheduled_at).toLocaleString("en-ZA")}</div>}
    </article>
  );
}

function Metric({ label, value, icon }: { label: string; value: string; icon: ReactNode }) {
  return <div className="card p-5"><div className="text-[var(--blue-dark)]">{icon}</div><div className="mt-4 text-2xl font-bold">{value}</div><div className="mt-1 text-sm text-[var(--muted)]">{label}</div></div>;
}

function nextAction(status: string) {
  const values: Record<string, string> = {
    awaiting_initial_payment: "Waiting for the opening fee",
    brief_submitted: "Qualify the family brief",
    awaiting_candidate_access: "Waiting for candidate access",
    search_active: "Invite and release suitable candidates",
    interviewing: "Coordinate interviews and feedback",
    trial: "Record the paid trial outcome",
    awaiting_success_fee: "Collect the successful-placement fee",
    placed: "Begin onboarding and guarantee check-ins",
  };
  return values[status] || niceStatus(status);
}

function requirements(placement: Placement) {
  return [placement.live_in && "Live-in", placement.drivers_license_required && "Driver's licence", placement.own_car_required && "Own car", placement.special_requirements].filter(Boolean).join(" · ") || "No additional requirements";
}

function scheduleInterview(placementId: number, candidateId: number, run: (label: string, path: string, body?: Record<string, unknown>) => Promise<void>) {
  const value = window.prompt("Interview date and time (YYYY-MM-DDTHH:MM)");
  if (value) void run("schedule", `/admin/permanent-placements/${placementId}/candidates/${candidateId}/schedule-interview`, { scheduled_at: value, interview_format: "video", interview_location: null, note: null });
}

function recordTrial(placementId: number, candidateId: number, run: (label: string, path: string, body?: Record<string, unknown>) => Promise<void>) {
  const value = window.prompt("Paid trial date and time (YYYY-MM-DDTHH:MM)");
  if (value) void run("trial", `/admin/permanent-placements/${placementId}/candidates/${candidateId}/stage`, { status: "trial", trial_scheduled_at: value, note: "Paid directly to the nanny" });
}

function recordPayment(placement: Placement, run: (label: string, path: string, body?: Record<string, unknown>) => Promise<void>) {
  const fee = placement.status === "awaiting_initial_payment" ? (placement.service_tier === "self_match" ? "activation" : "application") : placement.status === "awaiting_candidate_access" ? "candidate_access" : "success";
  const reason = window.prompt("Reason for recording this payment without Paystack");
  if (reason) void run("mark-paid", `/admin/permanent-placements/${placement.id}/payments/mark-paid`, { fee_type: fee, reason });
}
