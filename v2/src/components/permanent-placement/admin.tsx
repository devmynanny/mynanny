"use client";

import { apiJson, apiMediaUrl } from "@/lib/api";
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
import { ChangeEvent, ReactNode, useEffect, useState } from "react";
import {
  PlacementHeading,
  PlacementInfo,
  PlacementNotice,
} from "./shared";
import { Candidate, dateTime, money, niceStatus, Placement, Pricing } from "./types";

const weekdayNames = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

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

type PricingDraft = {
  self_match_activation: string;
  self_match_package: string;
  self_match_placement: string;
  concierge_consultation: string;
  concierge_engagement: string;
  concierge_success_balance: string;
  credit_activation: boolean;
};

type BillingSettings = {
  issuer_legal_name?: string | null;
  issuer_trading_name?: string | null;
  issuer_email?: string | null;
  issuer_phone?: string | null;
  issuer_address?: string | null;
  issuer_registration_number?: string | null;
  issuer_vat_number?: string | null;
  vat_registered: boolean;
  vat_rate_bps: number;
  prices_include_vat?: boolean | null;
  tax_status_confirmed: boolean;
  invoice_prefix: string;
  ready_to_issue: boolean;
  missing: string[];
};

function pricingDraft(pricing: Pricing): PricingDraft {
  const rand = (cents: number) => String(cents / 100);
  return {
    self_match_activation: rand(pricing.self_match.activation_fee_cents),
    self_match_package: rand(pricing.self_match.interview_package_fee_cents),
    self_match_placement: rand(pricing.self_match.success_fee_cents),
    concierge_consultation: rand(pricing.concierge.consultation_fee_cents),
    concierge_engagement: rand(pricing.concierge.engagement_fee_cents),
    concierge_success_balance: rand(pricing.concierge.success_balance_cents),
    credit_activation: pricing.self_match.activation_fee_credits_toward_package,
  };
}

export function AdminPermanentPlacements() {
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [detail, setDetail] = useState<Placement | null>(null);
  const [eligible, setEligible] = useState<EligibleNanny[]>([]);
  const [inviteNanny, setInviteNanny] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState("");
  const [prices, setPrices] = useState<PricingDraft | null>(null);
  const [billing, setBilling] = useState<BillingSettings | null>(null);

  async function load(selectId?: number) {
    const [next, nannies, billingSettings] = await Promise.all([
      apiJson<AdminOverview>("/admin/permanent-placements/overview"),
      apiJson<{ results: EligibleNanny[] }>(
        "/admin/permanent-placements/eligible-nannies",
      ),
      apiJson<BillingSettings>("/admin/billing/settings"),
    ]);
    setOverview(next);
    setPrices(pricingDraft(next.pricing));
    setEligible(nannies.results || []);
    setBilling(billingSettings);
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
      apiJson<BillingSettings>("/admin/billing/settings"),
    ])
      .then(([next, nannies, billingSettings]) => {
        setOverview(next);
        setPrices(pricingDraft(next.pricing));
        setEligible(nannies.results || []);
        setBilling(billingSettings);
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

  async function savePricing() {
    if (!prices) return;
    const cents = (value: string) => Math.round(Number(value) * 100);
    const amountFields = [
      prices.self_match_activation,
      prices.self_match_package,
      prices.self_match_placement,
      prices.concierge_consultation,
      prices.concierge_engagement,
      prices.concierge_success_balance,
    ];
    if (amountFields.some((value) => value.trim() === "" || Number(value) < 0 || !Number.isFinite(Number(value)))) {
      setMessage("Enter a valid amount of R0 or more in every pricing field.");
      return;
    }
    setBusy("save-pricing");
    try {
      await apiJson("/admin/permanent-placements/settings", {
        method: "PUT",
        body: JSON.stringify({
          self_match_activation_fee_cents: cents(prices.self_match_activation),
          self_match_interview_package_fee_cents: cents(prices.self_match_package),
          self_match_placement_fee_cents: cents(prices.self_match_placement),
          activation_fee_credits_toward_package: prices.credit_activation,
          concierge_consultation_fee_cents: cents(prices.concierge_consultation),
          concierge_engagement_fee_cents: cents(prices.concierge_engagement),
          concierge_success_balance_cents: cents(prices.concierge_success_balance),
        }),
      });
      setMessage("Permanent-placement pricing saved. Existing searches keep their original pricing.");
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to save placement pricing.");
    } finally {
      setBusy("");
    }
  }

  async function saveBilling() {
    if (!billing) return;
    setBusy("save-billing");
    try {
      const updated = await apiJson<BillingSettings>("/admin/billing/settings", {
        method: "PUT",
        body: JSON.stringify({
          issuer_legal_name: billing.issuer_legal_name || null,
          issuer_trading_name: billing.issuer_trading_name || "My Nanny",
          issuer_email: billing.issuer_email || null,
          issuer_phone: billing.issuer_phone || null,
          issuer_address: billing.issuer_address || null,
          issuer_registration_number: billing.issuer_registration_number || null,
          issuer_vat_number: billing.issuer_vat_number || null,
          vat_registered: billing.vat_registered,
          vat_rate_bps: billing.vat_rate_bps,
          prices_include_vat: billing.vat_registered ? billing.prices_include_vat === true : null,
          tax_status_confirmed: billing.tax_status_confirmed,
          invoice_prefix: billing.invoice_prefix || "MN",
        }),
      });
      setBilling(updated);
      setMessage(updated.ready_to_issue ? "Billing details saved. Invoices can now be issued." : `Billing draft saved. Still required: ${updated.missing.join(", ")}.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to save billing details.");
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
      {prices && (
        <PricingSettingsCard
          prices={prices}
          setPrices={setPrices}
          saving={busy === "save-pricing"}
          onSave={savePricing}
        />
      )}
      {billing && <BillingSettingsCard billing={billing} setBilling={setBilling} saving={busy === "save-billing"} onSave={saveBilling} />}
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

function PricingSettingsCard({
  prices,
  setPrices,
  saving,
  onSave,
}: {
  prices: PricingDraft;
  setPrices: (value: PricingDraft) => void;
  saving: boolean;
  onSave: () => Promise<void>;
}) {
  const topUp = prices.credit_activation
    ? Math.max(0, Number(prices.self_match_package) - Number(prices.self_match_activation))
    : Number(prices.self_match_package);
  const conciergeService = Number(prices.concierge_engagement) + Number(prices.concierge_success_balance);
  const field = (key: keyof Omit<PricingDraft, "credit_activation">) => ({
    value: prices[key],
    onChange: (event: ChangeEvent<HTMLInputElement>) =>
      setPrices({ ...prices, [key]: event.target.value }),
  });
  return (
    <section className="card mt-8 p-6 sm:p-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="eyebrow">Admin pricing</div>
          <h2 className="mt-2 text-2xl font-bold">Permanent-placement amounts</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--muted)]">
            These amounts apply only to new searches. Every existing search and payment keeps the pricing originally shown to that client.
          </p>
        </div>
        <button className="btn-primary" disabled={saving} onClick={() => void onSave()}>
          {saving ? <LoaderCircle className="animate-spin" size={17} /> : <Banknote size={17} />}
          Save pricing
        </button>
      </div>
      <div className="mt-7 grid gap-7 lg:grid-cols-2">
        <div>
          <h3 className="font-bold">Self-Match</h3>
          <div className="mt-4 grid gap-4 sm:grid-cols-3">
            <AmountField label="Search activation" {...field("self_match_activation")} />
            <AmountField label="Interview package total" {...field("self_match_package")} />
            <AmountField label="Successful placement" {...field("self_match_placement")} />
          </div>
          <label className="mt-4 flex items-start gap-3 text-sm leading-6">
            <input
              className="mt-1 size-4"
              type="checkbox"
              checked={prices.credit_activation}
              onChange={(event) => setPrices({ ...prices, credit_activation: event.target.checked })}
            />
            Credit the activation fee toward the interview package. With these figures, the next payment is {money(topUp * 100)}.
          </label>
        </div>
        <div>
          <h3 className="font-bold">Concierge</h3>
          <div className="mt-4 grid gap-4 sm:grid-cols-3">
            <AmountField label="Consultation" {...field("concierge_consultation")} />
            <AmountField label="Engagement invoice" {...field("concierge_engagement")} />
            <AmountField label="Placement balance" {...field("concierge_success_balance")} />
          </div>
          <p className="mt-4 text-sm leading-6 text-[var(--muted)]">
            The two planned placement invoices total {money(conciergeService * 100)}, excluding the consultation.
          </p>
        </div>
      </div>
    </section>
  );
}

function BillingSettingsCard({
  billing,
  setBilling,
  saving,
  onSave,
}: {
  billing: BillingSettings;
  setBilling: (value: BillingSettings) => void;
  saving: boolean;
  onSave: () => Promise<void>;
}) {
  const textField = (key: keyof BillingSettings) => ({
    value: String(billing[key] || ""),
    onChange: (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setBilling({ ...billing, [key]: event.target.value }),
  });
  return (
    <section className="card mt-8 p-6 sm:p-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div><div className="eyebrow">Invoice readiness</div><h2 className="mt-2 text-2xl font-bold">Billing identity and tax status</h2><p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--muted)]">These details are frozen into each issued PDF. Drafts cannot be issued or emailed until the legal identity and VAT status are confirmed.</p></div>
        <div className="flex items-center gap-3"><span className="pill">{billing.ready_to_issue ? "Ready to issue" : "Draft only"}</span><button className="btn-primary" disabled={saving} onClick={() => void onSave()}>{saving ? <LoaderCircle className="animate-spin" size={17} /> : <ShieldCheck size={17} />}Save billing setup</button></div>
      </div>
      {!billing.ready_to_issue && billing.missing.length > 0 && <div className="mt-5 rounded-xl bg-[#fffaf0] p-4 text-sm"><b>Still required:</b> {billing.missing.join(", ")}.</div>}
      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <label><span className="mb-2 block text-sm font-bold">Legal business name</span><input className="field" {...textField("issuer_legal_name")} /></label>
        <label><span className="mb-2 block text-sm font-bold">Trading name</span><input className="field" {...textField("issuer_trading_name")} /></label>
        <label><span className="mb-2 block text-sm font-bold">Invoice prefix</span><input className="field" {...textField("invoice_prefix")} /></label>
        <label><span className="mb-2 block text-sm font-bold">Billing email</span><input className="field" type="email" {...textField("issuer_email")} /></label>
        <label><span className="mb-2 block text-sm font-bold">Billing phone</span><input className="field" {...textField("issuer_phone")} /></label>
        <label><span className="mb-2 block text-sm font-bold">Registration number</span><input className="field" {...textField("issuer_registration_number")} /></label>
        <label className="sm:col-span-2 lg:col-span-3"><span className="mb-2 block text-sm font-bold">Business address</span><textarea className="field min-h-20" {...textField("issuer_address")} /></label>
      </div>
      <div className="mt-6 grid gap-4 rounded-2xl bg-[var(--blue-pale)] p-5 sm:grid-cols-2 lg:grid-cols-4">
        <label className="flex items-center gap-3 text-sm font-bold"><input type="checkbox" checked={billing.tax_status_confirmed} onChange={(event) => setBilling({ ...billing, tax_status_confirmed: event.target.checked })} />VAT status confirmed</label>
        <label className="flex items-center gap-3 text-sm font-bold"><input type="checkbox" checked={billing.vat_registered} onChange={(event) => setBilling({ ...billing, vat_registered: event.target.checked, prices_include_vat: event.target.checked ? billing.prices_include_vat : null })} />VAT registered</label>
        {billing.vat_registered && <label><span className="mb-2 block text-sm font-bold">VAT number</span><input className="field bg-white" {...textField("issuer_vat_number")} /></label>}
        {billing.vat_registered && <label><span className="mb-2 block text-sm font-bold">VAT rate</span><span className="flex items-center"><input className="field bg-white" min="0" max="100" step="0.01" type="number" value={billing.vat_rate_bps / 100} onChange={(event) => setBilling({ ...billing, vat_rate_bps: Math.round(Number(event.target.value) * 100) })} /><span className="-ml-8">%</span></span></label>}
        {billing.vat_registered && <label className="flex items-center gap-3 text-sm font-bold sm:col-span-2 lg:col-span-4"><input type="checkbox" checked={billing.prices_include_vat === true} onChange={(event) => setBilling({ ...billing, prices_include_vat: event.target.checked })} />The customer-facing fees above already include VAT</label>}
      </div>
    </section>
  );
}

function AmountField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (event: ChangeEvent<HTMLInputElement>) => void;
}) {
  return (
    <label>
      <span className="mb-2 block text-sm font-bold">{label}</span>
      <span className="flex items-center rounded-xl border border-[var(--line)] bg-white px-3 focus-within:border-[var(--blue)]">
        <span className="text-sm font-bold text-[var(--muted)]">R</span>
        <input className="min-w-0 flex-1 bg-transparent px-2 py-3 outline-none" min="0" step="1" type="number" value={value} onChange={onChange} />
      </span>
    </label>
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
            <div className="flex items-center justify-between"><div><div className="eyebrow">Candidate pipeline</div><h2 className="mt-2 text-3xl font-bold">Managed introductions</h2></div><span className="pill">{placement.candidates?.length || 0}</span></div>
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
            {["awaiting_initial_payment", "awaiting_candidate_access", "awaiting_engagement_payment", "awaiting_success_fee"].includes(placement.status) && <button className="btn-secondary" disabled={Boolean(busy)} onClick={() => recordPayment(placement, run)}>Record offline/test payment</button>}
            {placement.replacement_status === "requested" && <><button className="btn-primary" disabled={Boolean(busy)} onClick={() => void run("replacement-approved", `/admin/permanent-placements/${placement.id}/replacement`, { decision: "approved", note: "Replacement search approved within the cover period" })}>Approve replacement search</button><button className="btn-quiet text-red-700" disabled={Boolean(busy)} onClick={() => void run("replacement-declined", `/admin/permanent-placements/${placement.id}/replacement`, { decision: "declined", note: "Replacement request reviewed and declined" })}>Decline request</button></>}
          </div></div>
          <div className="card p-6"><div className="eyebrow">Interview credits</div><div className="mt-2 text-3xl font-bold">{placement.interview_credits.available} available</div><p className="mt-2 text-sm leading-6 text-[var(--muted)]">{placement.interview_credits.used} of {placement.interview_credits.included} accepted interviews used in this {placement.interview_credits.cycle > 0 ? "replacement" : "initial"} search.</p></div>
          <div className="card p-6"><div className="eyebrow">Fees</div><div className="mt-4 grid gap-3">{placement.payments.map((payment) => <div className="flex items-center justify-between rounded-2xl border border-[var(--line)] p-4" key={payment.id}><span><b className="block text-sm">{niceStatus(payment.fee_type)}</b><span className="text-xs text-[var(--muted)]">{money(payment.amount_cents)}</span></span>{payment.status === "paid" ? <BadgeCheck className="text-[var(--green)]" /> : <span className="pill">{niceStatus(payment.status)}</span>}</div>)}</div>{placement.invoices.length > 0 && <div className="mt-5 border-t border-[var(--line)] pt-5"><div className="text-sm font-bold">Documents</div><div className="mt-3 grid gap-3">{placement.invoices.map((invoice) => <div className="rounded-xl bg-[var(--blue-pale)] p-3 text-sm" key={invoice.id}><div className="flex items-center justify-between"><b>{invoice.invoice_number || "Invoice draft"}</b><span className="pill">{niceStatus(invoice.status)}</span></div><div className="mt-2 flex flex-wrap gap-3">{invoice.invoice_pdf_url && <a className="font-bold underline" href={apiMediaUrl(invoice.invoice_pdf_url)} target="_blank" rel="noreferrer">Invoice PDF</a>}{invoice.receipt_pdf_url && <a className="font-bold underline" href={apiMediaUrl(invoice.receipt_pdf_url)} target="_blank" rel="noreferrer">Receipt PDF</a>}<button className="font-bold underline" disabled={Boolean(busy)} onClick={() => void run(`invoice-${invoice.id}`, `/admin/invoices/${invoice.id}/issue`, { send_email: true })}>{invoice.invoice_pdf_url ? "Request email again" : "Issue document & request email"}</button></div></div>)}</div></div>}</div>
          <div className="card p-6"><div className="eyebrow">Placement rules</div><ul className="mt-4 grid gap-3 text-sm leading-6 text-[var(--muted)]"><li>Candidate contact details remain private and My Nanny mediates post-interview support.</li><li>Trial days and reasonable transport are paid directly to the nanny.</li><li>One admin-approved replacement is available within {placement.pricing[placement.service_tier].replacement_days} days.</li></ul></div>
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
        {candidate.status === "interview_requested" && <span className="pill">Awaiting nanny response</span>}
        {candidate.status === "interview_accepted" && <button className="btn-primary !min-h-9" disabled={Boolean(busy)} onClick={() => scheduleInterview(placement.id, candidate.id, run)}>Schedule interview</button>}
        {["interview_accepted", "interview_scheduled"].includes(candidate.status) && <button className="btn-quiet !min-h-9" disabled={Boolean(busy)} onClick={() => recordInterviewException(placement.id, candidate.id, "cancelled_by_nanny", run)}>Nanny cancelled</button>}
        {candidate.status === "interview_scheduled" && <button className="btn-quiet !min-h-9" disabled={Boolean(busy)} onClick={() => recordInterviewException(placement.id, candidate.id, "not_held", run)}>Interview not held</button>}
        {candidate.status === "trial_requested" && <span className="pill">Trial awaiting nanny</span>}
        {candidate.status === "trial_change_requested" && <span className="pill">Alternative trial date suggested</span>}
        {candidate.status === "offer_pending" && <span className="pill">Offer awaiting nanny</span>}
        {candidate.status === "offer_admin_support" && <span className="pill">Offer support needed</span>}
      </div>
      {candidate.interview_scheduled_at && <div className="mt-3 text-sm text-[var(--muted)]">Interview: {new Date(candidate.interview_scheduled_at).toLocaleString("en-ZA")}</div>}
      {candidate.trial_status && candidate.trial_status !== "not_requested" && <div className="mt-3 rounded-xl bg-[var(--blue-pale)] p-3 text-sm"><b>Trial · {niceStatus(candidate.trial_status)}</b><div className="mt-1 text-[var(--muted)]">{dateTime(candidate.trial_scheduled_at)} to {dateTime(candidate.trial_ends_at)}{candidate.trial_alternative_at ? ` · Suggested: ${dateTime(candidate.trial_alternative_at)}` : ""}</div></div>}
      {candidate.offer_status && candidate.offer_status !== "not_requested" && <div className="mt-3 rounded-xl bg-[var(--blue-pale)] p-3 text-sm"><b>Offer · {niceStatus(candidate.offer_status)}</b><div className="mt-1 text-[var(--muted)]">{money(candidate.offer_salary_cents)} monthly · Starts {candidate.offer_start_date || "to confirm"} · {(candidate.offer_working_days || []).map((day) => weekdayNames[day]).join(", ")} {candidate.offer_start_time}-{candidate.offer_end_time}</div></div>}
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
    awaiting_engagement_payment: "Waiting for the Concierge engagement payment",
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

function recordInterviewException(placementId: number, candidateId: number, outcome: "cancelled_by_nanny" | "not_held", run: (label: string, path: string, body?: Record<string, unknown>) => Promise<void>) {
  const reason = window.prompt(outcome === "cancelled_by_nanny" ? "Reason supplied by the nanny" : "Why did the interview not take place?");
  if (reason) void run(outcome, `/admin/permanent-placements/${placementId}/candidates/${candidateId}/interview-outcome`, { outcome, reason });
}

function recordPayment(placement: Placement, run: (label: string, path: string, body?: Record<string, unknown>) => Promise<void>) {
  const fee = placement.status === "awaiting_initial_payment" ? (placement.service_tier === "self_match" ? "activation" : "application") : placement.status === "awaiting_candidate_access" ? "candidate_access" : placement.status === "awaiting_engagement_payment" ? "engagement" : "success";
  const reason = window.prompt("Reason for recording this payment without Paystack");
  if (reason) void run("mark-paid", `/admin/permanent-placements/${placement.id}/payments/mark-paid`, { fee_type: fee, reason });
}
