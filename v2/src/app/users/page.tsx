"use client";

import { AuthenticatedPage } from "@/components/authenticated-page";
import { GoogleAddressInput } from "@/components/google-address-input";
import { apiFetch, apiJson, apiMediaUrl } from "@/lib/api";
import {
  BadgeCheck,
  BriefcaseBusiness,
  Camera,
  CalendarDays,
  Check,
  Clock,
  Database,
  FileText,
  LoaderCircle,
  MapPin,
  Search,
  Save,
  ShieldCheck,
  UserRound,
  Upload,
  Video,
  X,
} from "lucide-react";
import Image from "next/image";
import { useEffect, useState } from "react";

type UserRow = {
  id: number;
  name: string;
  email: string;
  phone?: string | null;
  role: string;
  is_admin: boolean;
  nanny_id?: number | null;
  approved?: boolean | null;
  application_status?: string | null;
  video_screening_complete?: boolean | null;
  location?: { label?: string | null };
  rating?: number | null;
  review_count?: number;
};
type Clip = { question_index: number; url: string; uploaded_at: string };
type NamedItem = { id: number; name: string };
type PreviousJob = {
  role?: string;
  employer?: string;
  period?: string;
  care_type?: string;
  kids_age_when_started?: string;
  disability_details?: string;
  reference_name?: string;
  reference_phone?: string;
  reference_relationship?: string;
};
type LatestBookingForm = {
  request_id: number;
  group_id: number;
  status?: string;
  received_at?: string;
  start_dt?: string;
  end_dt?: string;
  sleepover?: boolean;
  requested_nannies_count?: number;
  notes?: string | null;
  responsibilities?: string | null;
  adult_present?: string | null;
  booking_reason?: string | null;
  sleepover_expectations?: string | null;
  sleepover_reason?: string | null;
  kids_count?: number;
  meal_option?: string | null;
  food_restrictions?: string | null;
  dogs_info?: string | null;
  disclaimer_basic_upkeep?: boolean;
  disclaimer_medicine?: boolean;
  disclaimer_extra_hours?: boolean;
  disclaimer_transport?: boolean;
  location?: { label?: string | null; formatted_address?: string | null };
  pricing?: {
    wage_cents?: number | null;
    booking_fee_cents?: number | null;
    total_cents?: number | null;
  };
};
type Profile = Record<string, unknown> & {
  name?: string;
  phone?: string;
  phone_alt?: string;
  bio?: string;
  approved?: boolean;
  application_status?: string;
  admin_reason?: string;
  profile_photo_url?: string;
  video_screening_complete?: boolean;
  video_screening_submitted_at?: string;
  video_screening_clips?: Clip[];
  qualifications?: NamedItem[];
  tags?: NamedItem[];
  languages?: NamedItem[];
  previous_jobs?: PreviousJob[];
  certificate_urls?: string[];
  sa_id_document_url?: string;
  passport_document_url?: string;
  passport_expiry?: string;
  work_permit_document_url?: string;
  police_clearance_document_url?: string;
  drivers_license_document_url?: string;
  latest_booking_form?: LatestBookingForm | null;
  video_resubmission_requested?: boolean;
  document_approvals?: Record<
    string,
    {
      approved?: boolean;
      approved_at?: string;
      approved_by_user_id?: number;
      approved_expiry?: string;
    }
  >;
};
type Stats = {
  bookings_made_count: number;
  bookings_attended_count: number;
  total_bookings_count: number;
};
type Tab =
  "personal" | "legal" | "work" | "documents" | "interview" | "operations";

const questions = [
  "Tell us about yourself",
  "Why childcare?",
  "Handling the unexpected",
  "A great day with a child",
];

const genderOptions: [string, string][] = [
  ["", "Select gender"],
  ["Female", "Female"],
  ["Male", "Male"],
  ["Other", "Other"],
];
const ethnicityOptions: [string, string][] = [
  ["", "Select race / ethnicity"],
  ["Black", "Black"],
  ["Coloured", "Coloured"],
  ["Indian/Asian", "Indian / Asian"],
  ["White", "White"],
  ["Other", "Other"],
];
const nationalityOptions: [string, string][] = [
  ["", "Select nationality"],
  ...[
    "Angolan",
    "Botswanan",
    "Comorian",
    "Congolese (DRC)",
    "Eswatini",
    "Lesotho",
    "Madagascan",
    "Malawian",
    "Mauritian",
    "Mozambican",
    "Namibian",
    "Seychellois",
    "South African",
    "Tanzanian",
    "Zambian",
    "Zimbabwean",
  ].map((value) => [value, value] as [string, string]),
];

function canonicalOption(
  value: unknown,
  options: [string, string][],
): string {
  const raw = String(value || "").trim();
  return (
    options.find(
      ([option]) => option.toLowerCase() === raw.toLowerCase(),
    )?.[0] || raw
  );
}

export default function UsersPage() {
  const [users, setUsers] = useState<UserRow[]>([]);
  const [selected, setSelected] = useState<UserRow | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [query, setQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [roleChanging, setRoleChanging] = useState(false);
  const [error, setError] = useState("");
  async function load() {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (query.trim()) params.set("q", query.trim());
      if (roleFilter) params.set("role", roleFilter);
      const rows = await apiJson<UserRow[]>(`/admin/users?${params}`);
      setUsers(rows);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load users.");
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    apiJson<UserRow[]>("/admin/users")
      .then((rows) => {
        setUsers(rows);
        const requested = Number(
          new URLSearchParams(window.location.search).get("user"),
        );
        setSelected(
          rows.find((row) => row.id === requested) || rows[0] || null,
        );
      })
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Unable to load users."),
      )
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => {
    if (!selected) return;
    Promise.resolve().then(() => setDetailLoading(true));
    const path =
      selected.role === "nanny"
        ? `/admin/nannies/${selected.id}/profile`
        : selected.role === "parent"
          ? `/admin/parents/${selected.id}/profile`
          : `/admin/users/${selected.id}`;
    Promise.all([
      apiJson<Profile>(path),
      apiJson<Stats>(`/admin/users/${selected.id}/booking-stats`),
    ])
      .then(([details, bookingStats]) => {
        setProfile(details);
        setStats(bookingStats);
      })
      .catch((err) =>
        setError(
          err instanceof Error ? err.message : "Unable to load this record.",
        ),
      )
      .finally(() => setDetailLoading(false));
  }, [selected]);
  async function changeRole(nextRole: "parent" | "nanny") {
    if (!selected || selected.role === nextRole) return;
    const label = nextRole === "nanny" ? "nanny/candidate" : "parent";
    if (
      !window.confirm(
        `Change ${selected.name}'s account type to ${label}? Their existing records will be retained.`,
      )
    )
      return;
    setRoleChanging(true);
    setError("");
    try {
      const updated = await apiJson<UserRow>(
        `/admin/users/${selected.id}/role`,
        {
          method: "PATCH",
          body: JSON.stringify({ role: nextRole }),
        },
      );
      const merged = { ...selected, ...updated };
      setUsers((current) =>
        current.map((user) => (user.id === merged.id ? merged : user)),
      );
      setProfile(null);
      setSelected(merged);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to change this account type.",
      );
    } finally {
      setRoleChanging(false);
    }
  }
  return (
    <AuthenticatedPage>
      {(role) =>
        role !== "admin" ? (
          <Restricted />
        ) : (
          <div className="mx-auto max-w-[1400px]">
            <div className="eyebrow">Operations database</div>
            <h1 className="display mt-2 text-4xl sm:text-5xl">
              Users & records.
            </h1>
            <p className="mt-3 text-[var(--muted)]">
              Search every parent, candidate, nanny and administrator from one
              place.
            </p>
            <div className="card mt-7 flex flex-col gap-3 p-4 sm:flex-row">
              <label className="relative flex-1">
                <Search
                  className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400"
                  size={18}
                />
                <input
                  className="field !pl-11"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") void load();
                  }}
                  placeholder="Name, email, phone, ID or passport"
                />
              </label>
              <select
                className="field sm:max-w-48"
                value={roleFilter}
                onChange={(e) => setRoleFilter(e.target.value)}
              >
                <option value="">All account types</option>
                <option value="parent">Parents</option>
                <option value="nanny">Candidates & nannies</option>
                <option value="admin">Admins</option>
              </select>
              <button className="btn-primary" onClick={load}>
                Search records
              </button>
            </div>
            {error && (
              <div className="mt-4 rounded-xl bg-amber-50 p-3 text-sm text-amber-900">
                {error}
              </div>
            )}
            <div className="mt-6 grid min-h-[600px] gap-6 xl:grid-cols-[.62fr_1.38fr]">
              <UserList
                users={users}
                selected={selected}
                loading={loading}
                onSelect={setSelected}
              />
              <section className="card overflow-hidden">
                {!selected ? (
                  <EmptyRecord />
                ) : detailLoading ? (
                  <Loading />
                ) : profile ? (
                  <UserSummary
                    key={selected.id}
                    user={selected}
                    profile={profile}
                    stats={stats}
                    roleChanging={roleChanging}
                    onRoleChange={changeRole}
                  />
                ) : null}
              </section>
            </div>
          </div>
        )
      }
    </AuthenticatedPage>
  );
}

function UserList({
  users,
  selected,
  loading,
  onSelect,
}: {
  users: UserRow[];
  selected: UserRow | null;
  loading: boolean;
  onSelect: (user: UserRow) => void;
}) {
  return (
    <aside className="card max-h-[780px] overflow-auto p-3">
      <div className="flex items-center justify-between px-3 py-2 text-sm">
        <b>{users.length} users</b>
        {loading && <LoaderCircle className="animate-spin" size={17} />}
      </div>
      {users.map((user) => (
        <button
          key={user.id}
          onClick={() => onSelect(user)}
          className={`mb-1 flex w-full items-center gap-3 rounded-2xl p-3 text-left ${selected?.id === user.id ? "bg-[var(--blue-pale)]" : "hover:bg-slate-50"}`}
        >
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-white shadow">
            <UserRound size={18} />
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate font-bold">{user.name}</div>
            <div className="truncate text-xs text-[var(--muted)]">
              {user.email}
            </div>
            <div className="mt-1 flex flex-wrap gap-1">
              <span className="pill !px-2 !py-0.5 capitalize">
                {user.is_admin ? "admin" : user.role}
              </span>
              {user.role === "nanny" && (
                <span
                  className={`pill !px-2 !py-0.5 ${user.video_screening_complete ? "text-emerald-700" : "text-amber-700"}`}
                >
                  {user.video_screening_complete
                    ? "Video complete"
                    : "Video pending"}
                </span>
              )}
            </div>
          </div>
        </button>
      ))}
    </aside>
  );
}

function UserSummary({
  user,
  profile,
  stats,
  roleChanging,
  onRoleChange,
}: {
  user: UserRow;
  profile: Profile;
  stats: Stats | null;
  roleChanging: boolean;
  onRoleChange: (role: "parent" | "nanny") => void;
}) {
  const [drawer, setDrawer] = useState(false);
  const [photoUrl, setPhotoUrl] = useState(profile.profile_photo_url);
  const [photoStatus, setPhotoStatus] = useState("");
  async function uploadPhoto(file?: File) {
    if (!file) return;
    setPhotoStatus("Uploading...");
    const body = new FormData();
    body.append("file", file);
    const response = await apiFetch(`/admin/nannies/${user.id}/photo`, {
      method: "POST",
      body,
    });
    if (!response.ok) {
      setPhotoStatus(await response.text());
      return;
    }
    const result = await response.json();
    setPhotoUrl(result.url);
    setPhotoStatus("Photo updated.");
  }
  const completion =
    user.role === "nanny" ? candidateCompletion(profile) : null;
  return (
    <>
      <header className="border-b border-[var(--line)] bg-[var(--blue-pale)] p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-center gap-4">
            {photoUrl ? (
              <Image
                src={photoUrl}
                alt=""
                width={72}
                height={72}
                className="h-18 w-18 rounded-2xl object-cover"
                unoptimized
              />
            ) : (
              <div className="flex h-18 w-18 items-center justify-center rounded-2xl bg-white">
                <UserRound />
              </div>
            )}
            <div>
              <div className="eyebrow">User #{user.id}</div>
              <h2 className="mt-1 text-3xl font-bold">{user.name}</h2>
              <div className="mt-1 text-sm text-[var(--muted)]">
                {user.email}
              </div>
              {user.role === "nanny" && (
                <div className="mt-3 flex flex-wrap items-center gap-3">
                  <label className="btn-secondary !min-h-9 cursor-pointer !px-3 !py-1.5 text-xs">
                    <Camera size={15} />
                    {photoUrl ? "Replace photo" : "Upload photo"}
                    <input
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      className="sr-only"
                      onChange={(event) =>
                        void uploadPhoto(event.target.files?.[0])
                      }
                    />
                  </label>
                  {photoStatus && (
                    <span className="text-xs text-[var(--muted)]">
                      {photoStatus}
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <span className="pill capitalize">
              {user.is_admin ? "administrator" : user.role}
            </span>
            {user.role === "nanny" && (
              <span className="pill">
                <BadgeCheck size={14} />
                {profile.approved
                  ? "Approved"
                  : profile.application_status || "Pending"}
              </span>
            )}
            {!user.is_admin && (
              <label className="pill !bg-white">
                <span className="sr-only">Account type</span>
                <select
                  aria-label="Account type"
                  className="bg-transparent font-bold capitalize outline-none"
                  value={user.role}
                  disabled={roleChanging}
                  onChange={(event) =>
                    onRoleChange(event.target.value as "parent" | "nanny")
                  }
                >
                  <option value="parent">Parent account</option>
                  <option value="nanny">Nanny / candidate</option>
                </select>
              </label>
            )}
          </div>
        </div>
      </header>
      <div className="grid gap-6 p-6">
        <div className="grid gap-3 sm:grid-cols-3">
          {[
            ["Bookings", stats?.total_bookings_count || 0],
            ["Reviews", user.review_count || 0],
            ["Rating", user.rating?.toFixed(1) || "New"],
          ].map(([label, value]) => (
            <Metric key={String(label)} label={String(label)} value={value} />
          ))}
        </div>
        {user.role === "nanny" ? (
          <>
            {profile.video_resubmission_requested && (
              <section className="rounded-2xl border border-amber-200 bg-amber-50 p-5">
                <div className="flex flex-wrap items-center justify-between gap-4">
                  <div>
                    <div className="eyebrow !text-amber-800">
                      Action requested
                    </div>
                    <h3 className="mt-2 text-lg font-bold">
                      New video interview attempt
                    </h3>
                    <p className="mt-1 text-sm text-amber-900">
                      This nanny has asked to replace her submitted interview
                      videos.
                    </p>
                  </div>
                  <button
                    className="btn-primary"
                    onClick={async () => {
                      if (
                        !window.confirm(
                          "Approve a new interview attempt? Existing submitted clips will be cleared.",
                        )
                      )
                        return;
                      await apiJson(
                        `/admin/users/${user.id}/video-resubmission/approve`,
                        { method: "POST", body: "{}" },
                      );
                      window.location.reload();
                    }}
                  >
                    Approve new attempt
                  </button>
                </div>
              </section>
            )}
            <section className="rounded-2xl border border-[var(--line)] p-5">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <div className="eyebrow">Candidate file</div>
                  <h3 className="mt-2 text-xl font-bold">
                    {completion?.complete}/{completion?.total} required areas
                    complete
                  </h3>
                  <p className="mt-2 text-sm text-[var(--muted)]">
                    Identity, legal documents, childcare background,
                    preferences, interview and operational readiness.
                  </p>
                </div>
                <button className="btn-primary" onClick={() => setDrawer(true)}>
                  Open complete nanny file
                </button>
              </div>
              <div className="mt-5 h-2 overflow-hidden rounded-full bg-slate-100">
                <div
                  className="h-full rounded-full bg-[var(--green)]"
                  style={{ width: `${completion?.percent || 0}%` }}
                />
              </div>
              {completion && completion.missing.length > 0 && (
                <div className="mt-4 text-sm text-amber-800">
                  <b>Still needed:</b>{" "}
                  {completion.missing.slice(0, 5).join(", ")}
                  {completion.missing.length > 5
                    ? ` and ${completion.missing.length - 5} more`
                    : ""}
                </div>
              )}
            </section>
            <section>
              <SectionTitle
                icon={<Video size={18} />}
                title="Video interview"
              />
              <div className="mt-3 flex items-center gap-2 text-sm">
                <StatusDot ok={Boolean(profile.video_screening_complete)} />
                {profile.video_screening_complete
                  ? "Submitted and ready for review"
                  : "Not yet submitted"}
              </div>
            </section>
          </>
        ) : (
          <ParentSummary user={user} profile={profile} />
        )}
      </div>
      {drawer && (
        <CandidateDrawer
          user={user}
          profile={profile}
          stats={stats}
          onClose={() => setDrawer(false)}
        />
      )}
    </>
  );
}

function ParentSummary({ user, profile }: { user: UserRow; profile: Profile }) {
  const latest = profile.latest_booking_form;
  return (
    <div className="grid gap-8">
      <section>
        <SectionTitle icon={<UserRound size={18} />} title="Family profile" />
        <InfoGrid
          showMissing
          items={[
            ["Phone", profile.phone || user.phone],
            ["Preferred contact", profile.preferred_messaging_channel],
            ["Children", profile.kids_count],
            ["Children's ages", formatObjectList(profile.kids_ages)],
            ["Home language ID", profile.home_language_id],
            ["Residence", humanLabel(profile.residence_type)],
            [
              "Default location",
              profile.formatted_address ||
                profile.location_label ||
                user.location?.label,
            ],
            ["Access instructions", formatObjectList(profile.access_flags)],
            [
              "What matters in a nanny",
              formatObjectList(profile.desired_tag_ids),
            ],
            ["Family notes", profile.special_notes],
          ]}
        />
      </section>
      <section>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <SectionTitle
            icon={<CalendarDays size={18} />}
            title="Latest client booking form"
          />
          {latest && <span className="pill">Request #{latest.request_id}</span>}
        </div>
        {latest ? (
          <div className="mt-5 grid gap-5">
            <div className="rounded-2xl bg-[var(--blue-pale)] p-4">
              <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
                <span className="flex items-center gap-2">
                  <Clock size={15} />
                  <b>Received:</b> {formatDate(latest.received_at)}
                </span>
                <span className="capitalize">
                  <b>Status:</b> {humanLabel(latest.status)}
                </span>
                <span>
                  <b>Nannies requested:</b>{" "}
                  {latest.requested_nannies_count || 1}
                </span>
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="rounded-2xl border border-[var(--line)] p-4">
                <div className="flex items-center gap-2 font-bold">
                  <CalendarDays size={16} />
                  Schedule
                </div>
                <div className="mt-3 text-sm text-[var(--muted)]">
                  {formatBookingSchedule(latest)}
                </div>
              </div>
              <div className="rounded-2xl border border-[var(--line)] p-4">
                <div className="flex items-center gap-2 font-bold">
                  <MapPin size={16} />
                  Booking location
                </div>
                <div className="mt-3 text-sm text-[var(--muted)]">
                  {latest.location?.formatted_address ||
                    latest.location?.label ||
                    "Not recorded"}
                </div>
              </div>
            </div>
            <div className="rounded-2xl border border-[var(--line)] p-5">
              <h4 className="font-bold">Care instructions received</h4>
              <InfoGrid
                showMissing
                items={[
                  ["Nanny responsibilities", latest.responsibilities],
                  ["Adult present", humanLabel(latest.adult_present)],
                  ["Reason for booking", latest.booking_reason],
                  ["Children attending", latest.kids_count],
                  ["Meal arrangement", humanLabel(latest.meal_option)],
                  ["Food restrictions", latest.food_restrictions],
                  ["Dogs at home", humanLabel(latest.dogs_info)],
                  ["Sleepover", latest.sleepover ? "Yes" : "No"],
                  ["Sleepover expectations", latest.sleepover_expectations],
                  ["Sleepover reason", latest.sleepover_reason],
                  ["Additional notes", latest.notes],
                ]}
              />
            </div>
            <div className="rounded-2xl border border-[var(--line)] p-5">
              <h4 className="font-bold">Client acknowledgements</h4>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <Consent
                  ok={latest.disclaimer_basic_upkeep}
                  label="Child-related upkeep only"
                />
                <Consent
                  ok={latest.disclaimer_medicine}
                  label="Medicine instructions and consent"
                />
                <Consent
                  ok={latest.disclaimer_extra_hours}
                  label="Additional hours are chargeable"
                />
                <Consent
                  ok={latest.disclaimer_transport}
                  label="Safe transport after 17:00"
                />
              </div>
            </div>
            {latest.pricing && (
              <div className="rounded-2xl border border-[var(--line)] p-5">
                <h4 className="font-bold">Last quoted pricing</h4>
                <InfoGrid
                  items={[
                    ["Nanny wage", money(latest.pricing.wage_cents)],
                    ["Booking fee", money(latest.pricing.booking_fee_cents)],
                    ["Total", money(latest.pricing.total_cents)],
                  ]}
                />
              </div>
            )}
          </div>
        ) : (
          <div className="mt-5 rounded-2xl bg-slate-50 p-6 text-sm text-[var(--muted)]">
            No completed booking questionnaire has been received from this
            parent yet. Profile defaults remain available above.
          </div>
        )}
      </section>
    </div>
  );
}

function Consent({ ok, label }: { ok?: boolean; label: string }) {
  return (
    <div
      className={`flex items-center gap-3 rounded-xl p-3 text-sm font-bold ${ok ? "bg-emerald-50 text-emerald-800" : "bg-amber-50 text-amber-900"}`}
    >
      <StatusDot ok={Boolean(ok)} />
      {label}: {ok ? "Confirmed" : "Not confirmed"}
    </div>
  );
}
function humanLabel(value: unknown) {
  if (value === undefined || value === null || value === "") return null;
  return String(value)
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}
function formatObjectList(value: unknown) {
  if (!Array.isArray(value) || !value.length) return null;
  return value
    .map((item) =>
      typeof item === "object" && item !== null
        ? Object.values(item)
            .filter(
              (part) => part !== null && part !== undefined && part !== "",
            )
            .join(" ")
        : String(item),
    )
    .join(", ");
}
function formatBookingSchedule(form: LatestBookingForm) {
  if (!form.start_dt) return "Not recorded";
  const start = new Date(form.start_dt);
  const end = form.end_dt ? new Date(form.end_dt) : null;
  return `${start.toLocaleString("en-ZA", { dateStyle: "medium", timeStyle: "short" })}${end ? ` - ${end.toLocaleTimeString("en-ZA", { hour: "2-digit", minute: "2-digit" })}` : ""}${form.sleepover ? " · Sleepover" : ""}`;
}
function money(value?: number | null) {
  return value == null
    ? null
    : `R${(value / 100).toLocaleString("en-ZA", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function CandidateDrawer({
  user,
  profile,
  stats,
  onClose,
}: {
  user: UserRow;
  profile: Profile;
  stats: Stats | null;
  onClose: () => void;
}) {
  const [tab, setTab] = useState<Tab>("personal");
  const [record, setRecord] = useState(profile);
  async function refreshRecord() {
    const next = await apiJson<Profile>(`/admin/nannies/${user.id}/profile`);
    setRecord(next);
  }
  const tabs: [Tab, string][] = [
    ["personal", "Personal"],
    ["legal", "Identity & legal"],
    ["work", "Work & experience"],
    ["documents", "Documents"],
    ["interview", "Interview"],
    ["operations", "Operations"],
  ];
  return (
    <div
      className="fixed inset-0 z-50 bg-[var(--ink)]/35 backdrop-blur-sm"
      onMouseDown={onClose}
    >
      <aside
        className="ml-auto h-full w-full max-w-4xl overflow-auto bg-white shadow-2xl"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <header className="sticky top-0 z-10 border-b border-[var(--line)] bg-white/95 p-5 backdrop-blur">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="eyebrow">Complete candidate file</div>
              <h2 className="mt-1 text-2xl font-bold">{user.name}</h2>
              <div className="mt-1 text-sm text-[var(--muted)]">
                #{user.id} · {user.email}
              </div>
            </div>
            <button
              className="btn-quiet !min-h-10 !px-3"
              onClick={onClose}
              aria-label="Close candidate file"
            >
              <X />
            </button>
          </div>
          <nav className="mt-5 flex gap-2 overflow-x-auto pb-1">
            {tabs.map(([id, label]) => (
              <button
                key={id}
                onClick={() => setTab(id)}
                className={`whitespace-nowrap rounded-full px-4 py-2 text-sm font-bold ${tab === id ? "bg-[var(--blue-dark)] text-white" : "bg-slate-100 text-[var(--muted)]"}`}
              >
                {label}
              </button>
            ))}
          </nav>
        </header>
        <div className="p-5 sm:p-8">
          {tab === "personal" && (
            <PersonalPanel
              profile={record}
              user={user}
              onSaved={refreshRecord}
            />
          )}{" "}
          {tab === "legal" && (
            <LegalPanel
              profile={record}
              userId={user.id}
              onSaved={refreshRecord}
            />
          )}{" "}
          {tab === "work" && (
            <WorkPanel profile={record} userId={user.id} onSaved={refreshRecord} />
          )}{" "}
          {tab === "documents" && (
            <DocumentsPanel
              profile={record}
              userId={user.id}
              onChanged={refreshRecord}
            />
          )}{" "}
          {tab === "interview" && <InterviewPanel profile={record} />}{" "}
          {tab === "operations" && (
            <OperationsPanel profile={record} stats={stats} />
          )}
        </div>
      </aside>
    </div>
  );
}

function PersonalPanel({
  profile,
  user,
  onSaved,
}: {
  profile: Profile;
  user: UserRow;
  onSaved: () => Promise<void>;
}) {
  return (
    <AdminProfileForm
      userId={user.id}
      title="Personal, contact & household"
      icon={<UserRound />}
      onSaved={onSaved}
      initial={{
        full_name: profile.name || user.name,
        email: profile.email || user.email,
        phone: profile.phone || user.phone || "",
        phone_alt: profile.phone_alt || "",
        preferred_messaging_channel:
          profile.preferred_messaging_channel || "whatsapp",
        dob: profile.date_of_birth || "",
        gender: canonicalOption(profile.gender, genderOptions),
        ethnicity: canonicalOption(profile.ethnicity, ethnicityOptions),
        nationality: canonicalOption(profile.nationality, nationalityOptions),
        has_own_kids: profile.has_own_kids,
        own_kids_details: profile.own_kids_details || "",
        medical_conditions: profile.medical_conditions || "",
        formatted_address: profile.formatted_address || "",
        suburb: profile.suburb || "",
        city: profile.city || "",
        province: profile.province || "",
        postal_code: profile.postal_code || "",
        country: profile.country || "",
        lat: profile.lat ?? null,
        lng: profile.lng ?? null,
        bio: profile.bio || "",
      }}
      fields={[
        ["full_name", "Full name"],
        ["email", "Email", "email"],
        ["phone", "Primary phone", "tel"],
        ["phone_alt", "Alternative phone", "tel"],
        [
          "preferred_messaging_channel",
          "Preferred contact",
          "select",
          [
            ["whatsapp", "WhatsApp"],
            ["telegram", "Telegram"],
            ["email", "Email"],
            ["sms", "SMS"],
          ],
        ],
        ["dob", "Date of birth", "date"],
        ["gender", "Gender", "select", genderOptions],
        ["ethnicity", "Race / ethnicity", "select", ethnicityOptions],
        ["nationality", "Nationality", "select", nationalityOptions],
        ["has_own_kids", "Own children", "boolean"],
        ["own_kids_details", "Children details", "textarea"],
        ["medical_conditions", "Medical conditions / medication", "textarea"],
        ["bio", "Biography", "textarea"],
        ["formatted_address", "Home address"],
        ["suburb", "Suburb"],
        ["city", "City"],
        ["province", "Province"],
        ["postal_code", "Postal code"],
        ["country", "Country"],
      ]}
    />
  );
}

function LegalPanel({
  profile,
  userId,
  onSaved,
}: {
  profile: Profile;
  userId: number;
  onSaved: () => Promise<void>;
}) {
  const policeClearanceOptions: [string, string][] = [
    ["", "Not provided"],
    ["yes", "Yes"],
    ["not_yet", "No"],
  ];
  return (
    <AdminProfileForm
      userId={userId}
      title="Identity, immigration & compliance"
      icon={<ShieldCheck />}
      onSaved={onSaved}
      initial={{
        nationality: canonicalOption(profile.nationality, nationalityOptions),
        sa_id_number: profile.sa_id_number || "",
        passport_number: profile.passport_number || "",
        passport_expiry: profile.passport_expiry || "",
        permit_status: profile.permit_status || "",
        work_permit: profile.work_permit,
        work_permit_expiry: profile.work_permit_expiry || "",
        waiver: profile.waiver,
        police_clearance_status: canonicalOption(
          profile.police_clearance_status,
          policeClearanceOptions,
        ),
      }}
      fields={[
        ["nationality", "Nationality", "select", nationalityOptions],
        ["sa_id_number", "South African ID number"],
        ["passport_number", "Passport number"],
        ["passport_expiry", "Passport expiry", "date"],
        ["permit_status", "Permit / receipt status"],
        ["work_permit", "Work permit", "boolean"],
        ["work_permit_expiry", "Work permit expiry", "date"],
        ["waiver", "Waiver", "boolean"],
        [
          "police_clearance_status",
          "Police clearance status",
          "select",
          policeClearanceOptions,
        ],
      ]}
    />
  );
}

type AdminField = [string, string, string?, [string | number, string][]?];
function AdminProfileForm({
  userId,
  title,
  icon,
  initial,
  fields,
  onSaved,
}: {
  userId: number;
  title: string;
  icon: React.ReactNode;
  initial: Record<string, unknown>;
  fields: AdminField[];
  onSaved: () => Promise<void>;
}) {
  const [draft, setDraft] = useState(initial);
  const [editing, setEditing] = useState(false);
  const [status, setStatus] = useState("");
  async function save() {
    setStatus("Saving...");
    try {
      const payload = { ...draft };
      if (payload.dob === "") payload.dob = null;
      await apiJson(`/admin/nannies/${userId}/profile`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      await onSaved();
      setEditing(false);
      setStatus("Changes saved.");
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "Unable to save changes.");
    }
  }
  return (
    <Panel title={title} icon={icon}>
      <div className="mb-5 flex items-center justify-between gap-3">
        <span className="text-sm text-[var(--muted)]">
          Administrators can correct and complete this record.
        </span>
        <button
          className="btn-secondary !min-h-10"
          onClick={() => (editing ? void save() : setEditing(true))}
        >
          {editing ? <Save size={16} /> : null}
          {editing ? "Save changes" : "Edit details"}
        </button>
      </div>
      <div className="grid gap-5 sm:grid-cols-2">
        {fields.map(([key, label, type = "text", options]) =>
          editing && key === "formatted_address" ? (
            <div key={key}>
              <GoogleAddressInput
                label={label}
                value={String(draft.formatted_address ?? "")}
                onChange={(value) =>
                  setDraft((current) => ({
                    ...current,
                    formatted_address: value,
                    lat: null,
                    lng: null,
                  }))
                }
                onSelected={(address) =>
                  setDraft((current) => ({ ...current, ...address }))
                }
              />
            </div>
          ) : (
          <label key={key}>
            <span className="mb-2 block text-xs font-bold uppercase tracking-wider text-[var(--muted)]">
              {label}
            </span>
            {editing ? (
              type === "textarea" ? (
                <textarea
                  className="field min-h-24"
                  value={String(draft[key] ?? "")}
                  onChange={(e) =>
                    setDraft((v) => ({ ...v, [key]: e.target.value }))
                  }
                />
              ) : type === "boolean" ? (
                <select
                  className="field"
                  value={
                    draft[key] == null ? "" : draft[key] ? "true" : "false"
                  }
                  onChange={(e) =>
                    setDraft((v) => ({
                      ...v,
                      [key]:
                        e.target.value === ""
                          ? null
                          : e.target.value === "true",
                    }))
                  }
                >
                  <option value="">Not provided</option>
                  <option value="true">Yes</option>
                  <option value="false">No</option>
                </select>
              ) : type === "select" ? (
                <select
                  className="field"
                  value={String(draft[key] ?? "")}
                  onChange={(e) =>
                    setDraft((v) => ({ ...v, [key]: e.target.value }))
                  }
                >
                  {options?.map(([value, text]) => (
                    <option value={value} key={value}>
                      {text}
                    </option>
                  ))}
                </select>
              ) : type === "multiselect" ? (
                <div className="grid gap-2 rounded-2xl border border-[var(--line)] p-3 sm:grid-cols-2">
                  {options?.map(([value, text]) => {
                    const ids = Array.isArray(draft[key])
                      ? (draft[key] as unknown[]).map(Number)
                      : [];
                    return (
                      <label key={value} className="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={ids.includes(Number(value))}
                          onChange={(event) =>
                            setDraft((current) => ({
                              ...current,
                              [key]: event.target.checked
                                ? [...ids, Number(value)]
                                : ids.filter((id) => id !== Number(value)),
                            }))
                          }
                        />
                        {text}
                      </label>
                    );
                  })}
                </div>
              ) : (
                <input
                  className="field"
                  type={type}
                  value={String(draft[key] ?? "")}
                  onChange={(e) =>
                    setDraft((v) => ({ ...v, [key]: e.target.value }))
                  }
                />
              )
            ) : (
              <div
                className={`text-sm ${isMissing(draft[key]) ? "italic text-slate-400" : ""}`}
              >
                {isMissing(draft[key])
                  ? "Not provided"
                  : type === "boolean"
                    ? yesNo(draft[key])
                    : type === "multiselect"
                      ? options
                          ?.filter(([value]) =>
                            Array.isArray(draft[key]) &&
                            (draft[key] as unknown[])
                              .map(Number)
                              .includes(Number(value)),
                          )
                          .map(([, text]) => text)
                          .join(", ") || "Not provided"
                    : String(draft[key])}
              </div>
            )}
          </label>
          ),
        )}
      </div>
      {status && (
        <div
          role="status"
          className="mt-5 rounded-xl bg-[var(--blue-pale)] p-3 text-sm"
        >
          {status}
        </div>
      )}
    </Panel>
  );
}

function WorkPanel({
  profile,
  userId,
  onSaved,
}: {
  profile: Profile;
  userId: number;
  onSaved: () => Promise<void>;
}) {
  const jobs = profile.previous_jobs || [];
  const [catalogues, setCatalogues] = useState({
    qualifications: [] as NamedItem[],
    tags: [] as NamedItem[],
    languages: [] as NamedItem[],
  });
  useEffect(() => {
    let active = true;
    Promise.all([
      apiJson<NamedItem[]>("/qualifications"),
      apiJson<NamedItem[]>("/nanny-tags"),
      apiJson<NamedItem[]>("/languages"),
    ])
      .then(([qualifications, tags, languages]) => {
        if (active) setCatalogues({ qualifications, tags, languages });
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);
  const options = (items: NamedItem[]): [number, string][] =>
    items.map((item) => [item.id, item.name]);
  return (
    <div className="grid gap-8">
      <AdminProfileForm
        userId={userId}
        title="Work preferences & suitability"
        icon={<BriefcaseBusiness />}
        onSaved={onSaved}
        initial={{
          job_type: profile.job_type || "",
          current_job_availability: profile.current_job_availability || "",
          has_own_car: profile.has_own_car,
          has_drivers_license: profile.has_drivers_license,
          my_nanny_training_status: profile.my_nanny_training_status || "",
          dog_preference: profile.dog_preference || "",
          studying_details: profile.studying_details || "",
          qualification_ids: (profile.qualifications || []).map(({ id }) => id),
          tag_ids: (profile.tags || []).map(({ id }) => id),
          language_ids: (profile.languages || []).map(({ id }) => id),
        }}
        fields={[
          ["job_type", "Job type", "select", [["", "Not provided"], ["stay_in", "Stay in"], ["stay_out", "Stay out"], ["both", "Both"]]],
          ["current_job_availability", "Current availability", "select", [["", "Not provided"], ["piece_only", "Piece jobs only"], ["permanent_only", "Permanent work only"], ["piece_and_permanent", "Piece and permanent work"], ["unavailable", "Unavailable"]]],
          ["has_own_car", "Own car", "boolean"],
          ["has_drivers_license", "Driver's license", "boolean"],
          ["my_nanny_training_status", "My Nanny training", "select", [["", "Not provided"], ["yes", "Completed"], ["not_yet", "Not yet"]]],
          ["dog_preference", "Dog preference", "select", [["", "Not provided"], ["comfortable", "Comfortable with dogs"], ["not_comfortable", "Not comfortable with dogs"]]],
          ["studying_details", "Currently studying", "textarea"],
          ["qualification_ids", "Qualifications", "multiselect", options(catalogues.qualifications)],
          ["tag_ids", "Care experience", "multiselect", options(catalogues.tags)],
          ["language_ids", "Languages", "multiselect", options(catalogues.languages)],
        ]}
      />
      <PreviousJobsEditor
        jobs={jobs}
        userId={userId}
        onSaved={onSaved}
      />
    </div>
  );
}

const previousJobFields: [keyof PreviousJob, string][] = [
  ["role", "Role"],
  ["employer", "Employer / family"],
  ["period", "Period"],
  ["care_type", "Care provided"],
  ["kids_age_when_started", "Children's ages"],
  ["disability_details", "Disability care details"],
  ["reference_name", "Reference name"],
  ["reference_phone", "Reference phone"],
  ["reference_relationship", "Reference relationship"],
];

function PreviousJobsEditor({
  jobs,
  userId,
  onSaved,
}: {
  jobs: PreviousJob[];
  userId: number;
  onSaved: () => Promise<void>;
}) {
  const [draft, setDraft] = useState(jobs);
  const [editing, setEditing] = useState(false);
  const [status, setStatus] = useState("");
  async function save() {
    setStatus("Saving...");
    try {
      await apiJson(`/admin/nannies/${userId}/profile`, {
        method: "PATCH",
        body: JSON.stringify({ previous_jobs: draft }),
      });
      await onSaved();
      setEditing(false);
      setStatus("Previous jobs and references saved.");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Unable to save previous jobs.");
    }
  }
  return (
    <Panel
      title={`Previous jobs & references (${draft.length})`}
      icon={<BriefcaseBusiness />}
    >
      <div className="mb-5 flex flex-wrap justify-end gap-2">
        {editing && (
          <button
            className="btn-secondary !min-h-10"
            onClick={() => setDraft((current) => [...current, {}])}
          >
            Add previous job
          </button>
        )}
        <button
          className="btn-secondary !min-h-10"
          onClick={() => (editing ? void save() : setEditing(true))}
        >
          {editing ? <Save size={16} /> : null}
          {editing ? "Save changes" : "Edit jobs"}
        </button>
      </div>
      {draft.length ? (
        draft.map((job, index) => (
          <div key={index} className="mb-4 rounded-2xl border border-[var(--line)] p-5">
            <div className="mb-4 flex items-center justify-between gap-3">
              <h4 className="font-bold">{job.role || `Previous role ${index + 1}`}</h4>
              {editing && (
                <button
                  className="text-sm font-bold text-red-700"
                  onClick={() => setDraft((current) => current.filter((_, itemIndex) => itemIndex !== index))}
                >
                  Remove
                </button>
              )}
            </div>
            {editing ? (
              <div className="grid gap-4 sm:grid-cols-2">
                {previousJobFields.map(([key, label]) => (
                  <label key={key}>
                    <span className="mb-2 block text-xs font-bold uppercase tracking-wider text-[var(--muted)]">{label}</span>
                    <input
                      className="field"
                      value={job[key] || ""}
                      onChange={(event) =>
                        setDraft((current) => current.map((item, itemIndex) =>
                          itemIndex === index ? { ...item, [key]: event.target.value } : item,
                        ))
                      }
                    />
                  </label>
                ))}
              </div>
            ) : (
              <InfoGrid showMissing items={previousJobFields.map(([key, label]) => [label, job[key]])} />
            )}
          </div>
        ))
      ) : (
        <Empty text="No previous jobs or references recorded." />
      )}
      {status && <div role="status" className="mt-5 rounded-xl bg-[var(--blue-pale)] p-3 text-sm">{status}</div>}
    </Panel>
  );
}

function DocumentsPanel({
  profile,
  userId,
  onChanged,
}: {
  profile: Profile;
  userId: number;
  onChanged: () => Promise<void>;
}) {
  const [status, setStatus] = useState("");
  const docs: [string, string, string | undefined, string][] = [
    [
      "South African ID",
      "sa_id",
      profile.sa_id_document_url,
      "sa_id_document_url",
    ],
    [
      "Passport",
      "passport",
      profile.passport_document_url,
      "passport_document_url",
    ],
    [
      "Permit / waiver / receipt",
      "work_permit",
      profile.work_permit_document_url,
      "work_permit_document_url",
    ],
    [
      "Police clearance",
      "police_clearance",
      profile.police_clearance_document_url,
      "police_clearance_document_url",
    ],
    [
      "Driver's license",
      "drivers_license",
      profile.drivers_license_document_url,
      "drivers_license_document_url",
    ],
  ];
  const certificates = profile.certificate_urls || [];
  async function upload(type: string, file?: File) {
    if (!file) return;
    setStatus("Uploading document...");
    const body = new FormData();
    body.append("file", file);
    const response = await apiFetch(
      `/admin/nannies/${userId}/documents/${type}`,
      { method: "POST", body },
    );
    if (!response.ok) {
      setStatus(await response.text());
      return;
    }
    await onChanged();
    setStatus("Document uploaded and awaiting approval.");
  }
  async function approve(type: string, approved: boolean) {
    setStatus(approved ? "Approving document..." : "Removing approval...");
    try {
      await apiJson(
        `/admin/nannies/${userId}/documents/${type}/approval?approved=${approved}`,
        { method: "PATCH", body: "{}" },
      );
      await onChanged();
      setStatus(approved ? "Document approved." : "Document approval removed.");
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "Unable to update approval.");
    }
  }
  return (
    <Panel title="Uploaded documents" icon={<FileText />}>
      <p className="mb-5 text-sm text-[var(--muted)]">
        Upload documents for the candidate, review each file, and approve it
        without leaving this record.
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        {docs.map(([label, type, url, approvalKey]) => {
          const approved = Boolean(
            profile.document_approvals?.[approvalKey]?.approved,
          );
          return (
            <div
              key={label}
              className={`rounded-2xl border p-4 ${approved ? "border-amber-300 bg-amber-50/60" : "border-[var(--line)]"}`}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="font-bold">{label}</div>
                  <div
                    className={`mt-1 text-xs font-bold ${approved ? "text-amber-700" : url ? "text-emerald-700" : "text-slate-500"}`}
                  >
                    {approved
                      ? "Approved"
                      : url
                        ? "Uploaded · awaiting approval"
                        : "Not uploaded"}
                  </div>
                  {type === "passport" && (
                    <div className="mt-2 text-sm text-[var(--muted)]">
                      Expiry date: {profile.passport_expiry || "Not provided"}
                    </div>
                  )}
                </div>
                {approved && (
                  <BadgeCheck className="text-amber-600" size={22} />
                )}
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <label className="btn-secondary !min-h-10 cursor-pointer">
                  <Upload size={15} />
                  {url ? "Replace" : "Upload"}
                  <input
                    className="sr-only"
                    type="file"
                    accept="application/pdf,image/jpeg,image/png,image/webp"
                    onChange={(e) => void upload(type, e.target.files?.[0])}
                  />
                </label>
                {url && (
                  <a
                    className="btn-secondary !min-h-10"
                    href={url}
                    target="_blank"
                  >
                    Open
                  </a>
                )}
                {url && (
                  <button
                    className={
                      approved ? "btn-quiet !min-h-10" : "btn-primary !min-h-10"
                    }
                    onClick={() => void approve(type, !approved)}
                  >
                    {approved ? (
                      "Revoke approval"
                    ) : (
                      <>
                        <Check size={15} />
                        Approve
                      </>
                    )}
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
      <h4 className="mt-8 font-bold">Certificates ({certificates.length})</h4>
      {certificates.length ? (
        <div className="mt-3 flex flex-wrap gap-3">
          {certificates.map((url, index) => (
            <a key={url} className="btn-secondary" href={url} target="_blank">
              <FileText size={16} />
              Certificate {index + 1}
            </a>
          ))}
        </div>
      ) : (
        <Empty text="No certificates uploaded." />
      )}
      <label className="btn-secondary mt-4 cursor-pointer">
        <Upload size={16} />
        Upload certificate
        <input
          className="sr-only"
          type="file"
          accept="application/pdf,image/jpeg,image/png,image/webp"
          onChange={(e) => void upload("certificate", e.target.files?.[0])}
        />
      </label>
      {status && (
        <div
          role="status"
          className="mt-5 rounded-xl bg-[var(--blue-pale)] p-3 text-sm"
        >
          {status}
        </div>
      )}
    </Panel>
  );
}

function InterviewPanel({ profile }: { profile: Profile }) {
  const clips = profile.video_screening_clips || [];
  return (
    <Panel title="Recorded interview" icon={<Video />}>
      <div className="mb-5 flex items-center gap-2 text-sm">
        <StatusDot ok={Boolean(profile.video_screening_complete)} />
        {profile.video_screening_complete
          ? `Submitted ${formatDate(profile.video_screening_submitted_at)}`
          : "Not submitted"}
      </div>
      {clips.length ? (
        <div className="grid gap-4 sm:grid-cols-2">
          {clips.map((clip) => (
            <div
              key={clip.question_index}
              className="overflow-hidden rounded-2xl border border-[var(--line)]"
            >
              <video
                src={apiMediaUrl(clip.url)}
                controls
                preload="metadata"
                className="aspect-video w-full bg-black object-cover"
              />
              <div className="p-3 text-sm font-bold">
                {questions[clip.question_index] ||
                  `Question ${clip.question_index + 1}`}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <Empty text="No interview clips uploaded." />
      )}
    </Panel>
  );
}

function OperationsPanel({
  profile,
  stats,
}: {
  profile: Profile;
  stats: Stats | null;
}) {
  return (
    <Panel title="Application & operations" icon={<Database />}>
      <InfoGrid
        showMissing
        items={[
          ["Application status", profile.application_status],
          ["Approved", yesNo(profile.approved)],
          ["Admin reason / note", profile.admin_reason],
          ["Reviewed at", formatDate(profile.reviewed_at)],
          ["Reviewed by user", profile.reviewed_by_user_id],
          ["Profile complete", yesNo(profile.profile_complete)],
          ["Availability complete", yesNo(profile.availability_complete)],
          ["Banking complete", yesNo(profile.banking_complete)],
          ["Video complete", yesNo(profile.video_screening_complete)],
          ["Suspended", yesNo(profile.is_suspended)],
          ["Suspension reason", profile.suspension_reason],
          ["Bookings attended", stats?.bookings_attended_count],
          ["Cancellation count", profile.cancellation_count],
          ["No-show count", profile.no_show_count],
          [
            "Rating demerit",
            profile.rating_demerit_pct != null
              ? `${profile.rating_demerit_pct}%`
              : null,
          ],
        ]}
      />
    </Panel>
  );
}

function candidateCompletion(profile: Profile) {
  const required: [string, unknown][] = [
    ["profile photo", profile.profile_photo_url],
    ["phone", profile.phone],
    ["date of birth", profile.date_of_birth],
    ["gender", profile.gender],
    ["race / ethnicity", profile.ethnicity],
    ["nationality", profile.nationality],
    ["job type", profile.job_type],
    ["training status", profile.my_nanny_training_status],
    ["home address", profile.formatted_address],
    ["police clearance status", profile.police_clearance_status],
    ["identity number", profile.sa_id_number || profile.passport_number],
    [
      "identity document",
      profile.sa_id_document_url || profile.passport_document_url,
    ],
    ["video interview", profile.video_screening_complete],
    ["Paystack payout details", profile.banking_complete],
  ];
  const missing = required
    .filter(
      ([, value]) =>
        value === null ||
        value === undefined ||
        value === "" ||
        value === false,
    )
    .map(([label]) => label);
  return {
    complete: required.length - missing.length,
    total: required.length,
    missing,
    percent: Math.round(
      ((required.length - missing.length) / required.length) * 100,
    ),
  };
}
function Panel({
  title,
  icon,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section>
      <SectionTitle icon={icon} title={title} />
      <div className="mt-5">{children}</div>
    </section>
  );
}
function SectionTitle({
  icon,
  title,
}: {
  icon: React.ReactNode;
  title: string;
}) {
  return (
    <h3 className="flex items-center gap-2 border-b border-[var(--line)] pb-3 text-xl font-bold">
      {icon}
      {title}
    </h3>
  );
}
function InfoGrid({
  items,
  showMissing = false,
}: {
  items: [string, unknown][];
  showMissing?: boolean;
}) {
  const visible = showMissing
    ? items
    : items.filter(
        ([, value]) => value !== undefined && value !== null && value !== "",
      );
  return (
    <div className="grid gap-x-8 gap-y-5 sm:grid-cols-2">
      {visible.map(([label, value]) => (
        <div key={label}>
          <div className="text-xs font-bold uppercase tracking-wider text-[var(--muted)]">
            {label}
          </div>
          <div
            className={`mt-1 break-words text-sm ${isMissing(value) ? "italic text-slate-400" : ""}`}
          >
            {isMissing(value) ? "Not provided" : String(value)}
          </div>
        </div>
      ))}
    </div>
  );
}
function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-2xl border border-[var(--line)] p-4">
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-xs text-[var(--muted)]">{label}</div>
    </div>
  );
}
function StatusDot({ ok }: { ok: boolean }) {
  return (
    <span
      className={`h-2.5 w-2.5 rounded-full ${ok ? "bg-emerald-500" : "bg-amber-500"}`}
    />
  );
}
function Empty({ text }: { text: string }) {
  return (
    <div className="mt-3 rounded-xl bg-slate-50 p-4 text-sm text-[var(--muted)]">
      {text}
    </div>
  );
}
function Loading() {
  return (
    <div className="flex min-h-[500px] items-center justify-center">
      <LoaderCircle className="animate-spin" />
    </div>
  );
}
function EmptyRecord() {
  return (
    <div className="flex min-h-[500px] items-center justify-center text-[var(--muted)]">
      <Database className="mr-2" />
      Select a user record
    </div>
  );
}
function Restricted() {
  return (
    <div className="card mx-auto max-w-xl p-8 text-center">
      <h1 className="text-2xl font-bold">Team access only</h1>
    </div>
  );
}
function yesNo(value: unknown) {
  return value === true ? "Yes" : value === false ? "No" : null;
}
function isMissing(value: unknown) {
  return value === undefined || value === null || value === "";
}
function formatDate(value: unknown) {
  if (!value) return null;
  const date = new Date(String(value));
  return Number.isNaN(date.getTime())
    ? String(value)
    : date.toLocaleString("en-ZA", { dateStyle: "medium", timeStyle: "short" });
}
