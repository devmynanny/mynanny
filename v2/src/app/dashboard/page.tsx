"use client";

import { AppShell } from "@/components/app-shell";
import { CalendarEvent, MonthCalendar } from "@/components/month-calendar";
import { apiJson } from "@/lib/api";
import {
  CalendarDay,
  DayBookingsDrawer,
  OperationsOverview,
} from "@/app/bookings/page";
import {
  ArrowRight,
  Award,
  BadgeCheck,
  CalendarDays,
  CircleDashed,
  Landmark,
  Search,
  Sparkles,
  Video,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

type Me = {
  name: string;
  role: string;
  is_admin?: boolean;
  nanny_application_status?: string;
};
type NannyTrustProfile = {
  profile_photo_url?: string | null;
  nationality?: string | null;
  sa_id_document_url?: string | null;
  passport_document_url?: string | null;
  police_clearance_document_url?: string | null;
  drivers_license_document_url?: string | null;
  my_nanny_training_status?: string | null;
  full_name?: string | null;
  phone?: string | null;
  dob?: string | null;
  is_approved?: boolean;
};
type TrustBadge = { key: string; label: string; detail: string; required: boolean; parent_visible: boolean; ready: boolean; earned: boolean; href: "/profile" | "/interview" };
type ParentProfileStatus = {
  is_profile_complete: boolean;
  missing_fields: string[];
};
type BankingStatus = {
  banking_complete: boolean;
  accounts: { bank_name?: string | null; masked_account_number?: string | null }[];
};
export default function Dashboard() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [failed, setFailed] = useState(false);
  const [interviewSubmitted, setInterviewSubmitted] = useState(false);
  const [availability, setAvailability] = useState<
    { start_dt: string; type: "available" | "blocked" }[]
  >([]);
  const [trustProfile, setTrustProfile] = useState<NannyTrustProfile>({});
  const [trustBadges, setTrustBadges] = useState<TrustBadge[]>([]);
  const [bankingStatus, setBankingStatus] = useState<BankingStatus | null>(null);
  useEffect(() => {
    apiJson<Me>("/auth/me")
      .then(setMe)
      .catch(() => setFailed(true));
  }, []);
  useEffect(() => {
    if (failed) router.replace("/login");
  }, [failed, router]);
  useEffect(() => {
    if (me?.role !== "nanny") return;
    apiJson<{ video_screening_complete: boolean }>(
      "/nannies/me/video-screening",
    )
      .then((data) => setInterviewSubmitted(data.video_screening_complete))
      .catch(() => undefined);
    apiJson<{
      results: { start_dt: string; type: "available" | "blocked" }[];
    }>("/nannies/me/availability")
      .then((data) => setAvailability(data.results || []))
      .catch(() => undefined);
    apiJson<NannyTrustProfile>("/nannies/me/profile")
      .then(setTrustProfile)
      .catch(() => undefined);
    apiJson<{ badges: TrustBadge[] }>("/nannies/me/trust-badges")
      .then((data) => setTrustBadges(data.badges || []))
      .catch(() => undefined);
    apiJson<BankingStatus>("/nanny/banking")
      .then(setBankingStatus)
      .catch(() => undefined);
  }, [me]);
  if (failed) return null;
  if (!me)
    return (
      <main className="flex min-h-screen items-center justify-center text-[var(--muted)]">
        Loading your account...
      </main>
    );
  const role = me.is_admin ? "admin" : me.role === "nanny" ? "nanny" : "parent";
  return (
    <AppShell role={role} name={me.name}>
      {role === "parent" ? (
        <ParentHome name={me.name} />
      ) : role === "nanny" ? (
        <NannyHome
          name={me.name}
          interviewSubmitted={interviewSubmitted}
          availability={availability}
          trustProfile={trustProfile}
          trustBadges={trustBadges}
          bankingStatus={bankingStatus}
        />
      ) : (
        <AdminHome />
      )}
    </AppShell>
  );
}

function Heading({
  eyebrow,
  title,
  body,
}: {
  eyebrow: string;
  title: string;
  body: string;
}) {
  return (
    <div>
      <div className="eyebrow">{eyebrow}</div>
      <h1 className="display mt-2 text-4xl sm:text-5xl">{title}</h1>
      <p className="mt-3 max-w-2xl text-[var(--muted)]">{body}</p>
    </div>
  );
}
function ParentHome({ name }: { name: string }) {
  const first = name?.split(" ")[0] || "there";
  const [profileStatus, setProfileStatus] = useState<ParentProfileStatus | null>(
    null,
  );
  const [showSavedProfile, setShowSavedProfile] = useState(
    () =>
      typeof window !== "undefined" &&
      window.sessionStorage.getItem("parent-profile-saved") === "true",
  );
  const [profileNoticeLeaving, setProfileNoticeLeaving] = useState(false);
  useEffect(() => {
    window.sessionStorage.removeItem("parent-profile-saved");
    apiJson<ParentProfileStatus>("/parents/me/profile-status")
      .then(setProfileStatus)
      .catch(() => undefined);
  }, []);
  useEffect(() => {
    if (!showSavedProfile) return;
    const fadeTimer = window.setTimeout(
      () => setProfileNoticeLeaving(true),
      9200,
    );
    const removeTimer = window.setTimeout(
      () => setShowSavedProfile(false),
      10000,
    );
    return () => {
      window.clearTimeout(fadeTimer);
      window.clearTimeout(removeTimer);
    };
  }, [showSavedProfile]);
  return (
    <div className="mx-auto max-w-6xl">
      <Heading
        eyebrow="Parent home"
        title={`Hello, ${first}.`}
        body="What does your family need help with?"
      />
      {profileStatus?.is_profile_complete && showSavedProfile && (
        <div
          className={`overflow-hidden transition-all duration-700 ease-in-out ${
            profileNoticeLeaving
              ? "max-h-0 -translate-y-3 opacity-0"
              : "max-h-[1200px] translate-y-0 opacity-100"
          }`}
        >
          <ParentProfileProgress
            status={profileStatus}
            firstName={first}
            celebration
          />
        </div>
      )}
      {profileStatus && !profileStatus.is_profile_complete && (
        <ParentProfileProgress status={profileStatus} firstName={first} />
      )}
      <section className="mt-8 grid gap-5 md:grid-cols-2">
        <Link href="/caregivers" className="card group p-6 sm:p-8">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[var(--blue-pale)] text-[var(--blue-dark)]">
            <Search />
          </div>
          <h2 className="mt-6 text-2xl font-bold">Find a nanny</h2>
          <p className="mt-2 leading-7 text-[var(--muted)]">
            Search by location, watch video introductions and choose who feels
            right.
          </p>
          <div className="mt-6 flex items-center gap-2 text-sm font-bold text-[var(--blue-dark)]">
            Start searching <ArrowRight size={17} />
          </div>
        </Link>
        <Link href="/bookings" className="card group p-6 sm:p-8">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#fff0ea] text-[var(--coral)]">
            <CalendarDays />
          </div>
          <h2 className="mt-6 text-2xl font-bold">Make a booking</h2>
          <p className="mt-2 leading-7 text-[var(--muted)]">
            Choose one date or plan recurring care around your family’s
            schedule.
          </p>
          <div className="mt-6 flex items-center gap-2 text-sm font-bold text-[var(--blue-dark)]">
            Choose dates <ArrowRight size={17} />
          </div>
        </Link>
      </section>
      <section className="card mt-6 p-6">
        <div className="flex items-center justify-between">
          <div>
            <div className="eyebrow">Your next booking</div>
            <h2 className="mt-2 text-xl font-bold">No upcoming care booked</h2>
          </div>
          <Sparkles className="text-[var(--blue)]" />
        </div>
        <p className="mt-2 text-sm text-[var(--muted)]">
          When a nanny accepts your request, all the details will appear here.
        </p>
      </section>
    </div>
  );
}

const parentProfileSteps = [
  {
    key: "phone",
    title: "Contact ready",
    detail: "Add a reliable phone number",
  },
  {
    key: "kids_count",
    title: "Family size",
    detail: "Tell us how many children need care",
  },
  {
    key: "kids_ages",
    title: "Children's ages",
    detail: "Help nannies prepare age-appropriate care",
  },
  {
    key: "desired_tag_ids",
    title: "Care needs",
    detail: "Choose the experience your family needs",
  },
  {
    key: "home_language_id",
    title: "Home language",
    detail: "Make communication and matching easier",
  },
  {
    key: "residence_type",
    title: "Home access",
    detail: "Share the type of residence",
  },
  {
    key: "location",
    title: "Location saved",
    detail: "Enable accurate distance-based matching",
  },
  {
    key: "default_location",
    title: "Default location",
    detail: "Choose your usual booking address",
  },
  {
    key: "payment_authorisation",
    title: "Booking payment ready",
    detail: "Authorise Paystack before requesting a booking",
  },
];

function ParentProfileProgress({
  status,
  firstName,
  celebration = false,
}: {
  status: ParentProfileStatus;
  firstName: string;
  celebration?: boolean;
}) {
  const missing = new Set(status.missing_fields);
  const noProfile = missing.has("profile");
  const completed = noProfile
    ? 0
    : parentProfileSteps.filter((step) => !missing.has(step.key)).length;
  const percent = Math.round((completed / parentProfileSteps.length) * 100);
  const next = noProfile
    ? parentProfileSteps[0]
    : parentProfileSteps.find((step) => missing.has(step.key));
  return (
    <section className="card mt-8 overflow-hidden">
      <div className="bg-[linear-gradient(135deg,var(--blue-pale),#f6fbf8)] p-6 sm:p-7">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-white text-[var(--green)] shadow-sm">
              <Award />
            </span>
            <div>
              <h2 className="text-xl font-bold">
                {celebration
                  ? `Your family profile is 100% complete, ${firstName}`
                  : `Build your family profile, ${firstName}`}
              </h2>
              <p className="mt-1 text-sm text-[var(--muted)]">
                {celebration
                  ? "Everything is ready for faster matching and easier bookings."
                  : "A complete profile makes matching and future bookings faster."}
              </p>
            </div>
          </div>
          <span className="pill !bg-white">{percent}% complete</span>
        </div>
        <div className="mt-5 h-2.5 overflow-hidden rounded-full bg-white">
          <div
            className="h-full rounded-full bg-[var(--green)] transition-all duration-500"
            style={{ width: `${percent}%` }}
          />
        </div>
        <div className="mt-3 flex justify-between text-xs font-bold text-[var(--muted)]">
          <span>{completed} of {parentProfileSteps.length} steps complete</span>
          <span>{parentProfileSteps.length - completed} to go</span>
        </div>
      </div>
      <div className="grid gap-2 p-4 sm:grid-cols-2 lg:grid-cols-4">
        {parentProfileSteps.map((step) => {
          const complete = !noProfile && !missing.has(step.key);
          return (
            <div
              key={step.key}
              className={`flex items-start gap-3 rounded-xl p-3 ${complete ? "bg-emerald-50" : "bg-slate-50"}`}
            >
              {complete ? (
                <BadgeCheck className="shrink-0 text-[var(--green)]" size={19} />
              ) : (
                <CircleDashed className="shrink-0 text-slate-400" size={19} />
              )}
              <span>
                <b className="block text-sm">{step.title}</b>
                <small className="text-[var(--muted)]">{step.detail}</small>
              </span>
            </div>
          );
        })}
      </div>
      {celebration ? (
        <div className="border-t border-[var(--line)] bg-emerald-50 p-5 text-sm text-emerald-950">
          <b>All done.</b> If you need to change anything later, choose Profile
          from the menu.
        </div>
      ) : (
        <Link
          href="/profile"
          className="flex items-center justify-between gap-4 border-t border-[var(--line)] p-5 font-bold text-[var(--blue-dark)]"
        >
          <span>
            {next
              ? `Next best step: ${next.title}`
              : "Complete your family profile"}
          </span>
          <span className="flex items-center gap-2">
            Continue <ArrowRight size={17} />
          </span>
        </Link>
      )}
    </section>
  );
}
function NannyHome({
  name,
  interviewSubmitted,
  availability,
  trustProfile,
  trustBadges,
  bankingStatus,
}: {
  name: string;
  interviewSubmitted: boolean;
  availability: { start_dt: string; type: "available" | "blocked" }[];
  trustProfile: NannyTrustProfile;
  trustBadges: TrustBadge[];
  bankingStatus: BankingStatus | null;
}) {
  const events: CalendarEvent[] = availability.map((row) => ({
    date: row.start_dt.slice(0, 10),
    label: row.type === "available" ? "Available" : "Unavailable",
    tone: row.type === "available" ? "green" : "coral",
  }));
  return (
    <div className="mx-auto max-w-6xl">
      <Heading
        eyebrow="Nanny home"
        title={`Welcome, ${name?.split(" ")[0] || "there"}.`}
        body="Your screening, bookings and availability in one place."
      />
      <div className="mt-8 grid gap-6 xl:grid-cols-[.72fr_1.28fr]">
        <div className="grid content-start gap-5">
          {!interviewSubmitted && (
            <Link
              href="/interview"
              className="card bg-[var(--blue-dark)] p-6 text-white"
            >
              <Video size={26} />
              <div className="mt-5 text-xs font-extrabold uppercase tracking-widest text-white/60">
                Important next step
              </div>
              <h2 className="mt-2 text-2xl font-bold">
                Complete your video interview
              </h2>
              <p className="mt-2 leading-7 text-white/70">
                Parents can only discover your profile after your video has been
                completed and approved.
              </p>
              <div className="mt-6 inline-flex items-center gap-2 font-bold">
                Continue interview <ArrowRight size={17} />
              </div>
            </Link>
          )}
          <Link
            href="/payout-details"
            className={`card p-6 transition hover:-translate-y-0.5 ${bankingStatus?.banking_complete ? "bg-emerald-50" : "bg-amber-50"}`}
          >
            <div className="flex items-start gap-4">
              <span className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-white ${bankingStatus?.banking_complete ? "text-[var(--green)]" : "text-amber-700"}`}>
                <Landmark />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h2 className="font-bold">Payout details</h2>
                  <span className="text-xs font-bold">
                    {bankingStatus?.banking_complete ? "Ready" : "Required"}
                  </span>
                </div>
                <p className="mt-1 text-sm leading-6 text-[var(--muted)]">
                  {bankingStatus?.banking_complete
                    ? `${bankingStatus.accounts[0]?.bank_name || "Bank account"} ${bankingStatus.accounts[0]?.masked_account_number || ""}`
                    : "Add your bank account so Paystack can send your earnings."}
                </p>
                <span className="mt-3 inline-flex items-center gap-2 text-sm font-bold text-[var(--blue-dark)]">
                  {bankingStatus?.banking_complete ? "View payout details" : "Set up payouts"} <ArrowRight size={16} />
                </span>
              </div>
            </div>
          </Link>
          <TrustBadges
            profile={trustProfile}
            interviewSubmitted={interviewSubmitted}
            badges={trustBadges}
          />
        </div>
        <div className="card p-5">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <div className="eyebrow">Schedule</div>
              <h2 className="mt-1 text-xl font-bold">Your calendar</h2>
            </div>
            <Link href="/availability" className="btn-secondary !min-h-10">
              Edit availability
            </Link>
          </div>
          <MonthCalendar events={events} />
        </div>
      </div>
    </div>
  );
}

function TrustBadges({
  profile,
  interviewSubmitted,
  badges,
}: {
  profile: NannyTrustProfile;
  interviewSubmitted: boolean;
  badges: TrustBadge[];
}) {
  void profile;
  void interviewSubmitted;
  const earned = badges.filter((badge) => badge.earned).length;
  const next = badges.find((badge) => !badge.ready);
  const awaitingApproval = badges.some((badge) => badge.ready && !badge.earned);
  return (
    <div className="card overflow-hidden">
      <div className="bg-[linear-gradient(135deg,var(--blue-pale),#f6fbf8)] p-6">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-white text-[var(--green)] shadow-sm">
              <Award />
            </span>
            <div>
              <div className="font-bold">Your trust badges</div>
              <div className="text-sm text-[var(--muted)]">
                {earned} of {badges.length} earned
              </div>
            </div>
          </div>
          <span className="pill !bg-white">
            {earned}/{badges.length}
          </span>
        </div>
        <div className="mt-5 h-2 overflow-hidden rounded-full bg-white">
          <div
            className="h-full rounded-full bg-[var(--green)] transition-all"
            style={{ width: `${badges.length ? (earned / badges.length) * 100 : 0}%` }}
          />
        </div>
      </div>
      <div className="grid gap-2 p-4 sm:grid-cols-2 xl:grid-cols-1">
        {badges.map((badge) => (
          <Link
            key={badge.key}
            href={badge.href}
            className={`flex items-center gap-3 rounded-xl p-3 transition ${badge.earned ? "bg-emerald-50 text-emerald-900" : badge.ready ? "bg-amber-50 text-amber-950" : "hover:bg-[var(--blue-pale)]"}`}
          >
            {badge.earned ? (
              <BadgeCheck className="shrink-0 text-[var(--green)]" size={20} />
            ) : badge.ready ? (
              <CircleDashed className="shrink-0 text-amber-600" size={20} />
            ) : (
              <CircleDashed className="shrink-0 text-slate-400" size={20} />
            )}
            <span className="min-w-0 flex-1">
              <b className="block text-sm">{badge.label}{badge.required ? " *" : ""}</b>
              <small className="text-[var(--muted)]">{badge.detail}</small>
            </span>
            <span className="text-xs font-bold">
              {badge.earned
                ? "Earned"
                : badge.ready
                  ? "Awaiting approval"
                  : "Improve"}
            </span>
          </Link>
        ))}
      </div>
      {next && (
        <Link
          href={next.href}
          className="flex items-center justify-between gap-3 border-t border-[var(--line)] p-5 text-sm"
        >
          <span>
            <b>Next best step:</b> {next.label}
          </span>
          <ArrowRight size={17} />
        </Link>
      )}
      {awaitingApproval && (
        <div className="border-t border-[var(--line)] bg-amber-50 p-5 text-sm text-amber-950">
          <b>Evidence received.</b> Badges are awarded individually after the My Nanny team approves the relevant evidence.
        </div>
      )}
    </div>
  );
}

function adminWelcome() {
  const now = new Date();
  const parts = new Intl.DateTimeFormat("en-ZA", {
    timeZone: "Africa/Johannesburg",
    hour: "numeric",
    hourCycle: "h23",
    weekday: "long",
    day: "numeric",
  }).formatToParts(now);
  const hour = Number(parts.find((part) => part.type === "hour")?.value || 12);
  const day = Number(parts.find((part) => part.type === "day")?.value || 1);
  const weekday = parts.find((part) => part.type === "weekday")?.value || "";
  const period = hour < 12 ? "morning" : hour < 17 ? "afternoon" : "evening";
  const messages =
    period === "morning"
      ? [
          `Set up a calm ${weekday} by clearing priority screenings first.`,
          "A focused start makes the rest of operations easier.",
          "Review new candidates and prepare today’s care schedule.",
        ]
      : period === "afternoon"
        ? [
            `Keep this ${weekday} moving by closing the most important reviews.`,
            "Check active bookings, then clear the next candidate decisions.",
            "A quick review now keeps families and nannies moving forward.",
          ]
        : [
            `Wrap up ${weekday} with tomorrow’s priorities already clear.`,
            "Review anything urgent and leave the queue ready for tomorrow.",
            "Close the day with bookings settled and follow-ups assigned.",
          ];
  return {
    title: `Good ${period}.`,
    body: messages[(day + hour) % messages.length],
  };
}

function AdminHome() {
  const [selectedBookingDay, setSelectedBookingDay] =
    useState<CalendarDay | null>(null);
  const [selectedBookingId, setSelectedBookingId] = useState<number | null>(
    null,
  );
  const [bookingOverview, setBookingOverview] =
    useState<OperationsOverview | null>(null);
  useEffect(() => {
    apiJson<OperationsOverview>("/admin/bookings/overview")
      .then(setBookingOverview)
      .catch(() => undefined);
  }, []);
  function openBooking(id: number) {
    const day = bookingOverview?.month_calendar.days.find((item) =>
      item.bookings.some(
        (booking) => booking.booking_id === id || booking.request_id === id,
      ),
    );
    if (!day) return;
    setSelectedBookingId(id);
    setSelectedBookingDay(day);
  }
  const welcome = adminWelcome();
  const metrics = [
    {
      value: "12",
      label: "Interviews to review",
      Icon: Video,
      href: "/review" as const,
      action: "Open review queue",
    },
    {
      value: "3",
      label: "Bookings today",
      Icon: CalendarDays,
      href: "/bookings" as const,
      action: "Open bookings",
    },
  ];
  return (
    <div className="mx-auto max-w-6xl">
      <Heading eyebrow="Operations" title={welcome.title} body={welcome.body} />
      <div className="mt-8 grid gap-4 sm:grid-cols-2">
        {metrics.map(({ value, label, Icon, href, action }) => {
          const content = (
            <>
              <Icon className="text-[var(--blue-dark)]" />
              <div className="mt-5 text-3xl font-bold">{value}</div>
              <div className="mt-1 text-sm text-[var(--muted)]">{label}</div>
              {href && (
                <div className="mt-5 flex items-center gap-2 text-sm font-bold text-[var(--blue-dark)]">
                  {action} <ArrowRight size={16} />
                </div>
              )}
            </>
          );
          return href ? (
            <Link className="card group p-5" href={href} key={label}>
              {content}
            </Link>
          ) : (
            <div className="card p-5" key={label}>
              {content}
            </div>
          );
        })}
      </div>
      <div className="card mt-6 p-6">
        <div>
          <div className="eyebrow">Today</div>
          <h2 className="mt-2 text-xl font-bold">Booking operations</h2>
        </div>
        <div className="mt-5 grid gap-3">
          {[
            {
              id: 21,
              time: "14:00",
              title: "Test Nanny with Mariette",
              status: "In progress",
            },
            {
              id: 22,
              time: "15:30",
              title: "Nanny Two with David Diener",
              status: "Confirmed",
            },
            {
              id: 23,
              time: "18:00",
              title: "Nanny Three with MM Mynhardt",
              status: "Confirmed",
            },
          ].map(({ id, time, title, status }) => (
            <button
              type="button"
              onClick={() => openBooking(id)}
              key={id}
              className="group flex w-full flex-wrap items-center gap-4 rounded-2xl border border-[var(--line)] p-4 text-left transition hover:-translate-y-0.5 hover:border-[var(--blue)] hover:shadow-md disabled:cursor-wait disabled:opacity-60"
              disabled={!bookingOverview}
            >
              <div className="font-bold">{time}</div>
              <div className="min-w-[220px] flex-1 text-sm">{title}</div>
              <span className="pill">{status}</span>
              <ArrowRight className="text-[var(--blue-dark)]" size={17} />
            </button>
          ))}
        </div>
      </div>
      {selectedBookingDay && (
        <DayBookingsDrawer
          day={selectedBookingDay}
          initialBookingId={selectedBookingId}
          onClose={() => {
            setSelectedBookingDay(null);
            setSelectedBookingId(null);
          }}
        />
      )}
    </div>
  );
}
