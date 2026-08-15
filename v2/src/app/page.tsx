import { Brand } from "@/components/brand";
import { PoweredByTiqet } from "@/components/powered-by-tiqet";
import {
  ArrowRight,
  BadgeCheck,
  CalendarDays,
  Check,
  Heart,
  MapPin,
  MessageCircle,
  Play,
  ShieldCheck,
  Sparkles,
  Star,
  UserRoundCheck,
} from "lucide-react";
import Link from "next/link";

const parentSteps = [
  {
    title: "Tell us what your family needs",
    detail: "Choose your dates, times, care requirements and location.",
  },
  {
    title: "Meet nannies before you choose",
    detail: "Watch real video introductions and review verified trust badges.",
  },
  {
    title: "Book and stay connected",
    detail: "Send a request, receive updates and manage care in one place.",
  },
];

const faqs = [
  {
    question: "How are My Nanny caregivers screened?",
    answer:
      "Every nanny visible to parents has completed a video introduction and an administrative review. Identity, supporting documents and trust badges are only marked as verified after approval by the My Nanny team.",
  },
  {
    question: "Can I book for more than one date?",
    answer:
      "Yes. You can select one or more dates, specify the hours and care requirements, and then see nannies who are available for that booking.",
  },
  {
    question: "Can I arrange overnight care?",
    answer:
      "Yes. Sleepover bookings include dedicated fields for overnight expectations, routines and the reason care is required, so the nanny knows what to expect.",
  },
  {
    question: "Are contact and payment details secure?",
    answer:
      "Personal contact details are protected inside the platform. Payment authorisation is handled securely by Paystack; My Nanny does not store full card details.",
  },
];

export default function Home() {
  return (
    <main className="overflow-hidden bg-[#fffdf9]">
      <header className="relative z-20 mx-auto flex min-h-28 w-full max-w-[1440px] items-center justify-between px-5 py-4 sm:px-9 lg:px-14">
        <Brand home />
        <nav aria-label="Main navigation" className="flex items-center gap-1 sm:gap-2">
          <Link className="btn-quiet desktop-only" href="#how-it-works">
            How it works
          </Link>
          <Link className="btn-quiet desktop-only" href="#why-my-nanny">
            Why My Nanny
          </Link>
          <Link className="btn-secondary" href="/login">
            Log in
          </Link>
        </nav>
      </header>

      <section className="relative mx-auto grid min-h-[680px] max-w-[1440px] items-center gap-12 px-5 pb-20 pt-8 sm:px-9 lg:grid-cols-[1.04fr_.96fr] lg:px-14 lg:pb-28 lg:pt-12">
        <div className="pointer-events-none absolute -left-44 top-32 h-[460px] w-[460px] rounded-full bg-[#f8dad2]/45 blur-3xl" />
        <div className="rise relative z-10 max-w-3xl">
          <div className="eyebrow mb-5">Carefully chosen. Close to home.</div>
          <h1 className="display max-w-[760px] text-[clamp(3.4rem,7vw,7rem)] leading-[.88] text-[var(--ink)]">
            Care that feels like family.
          </h1>
          <p className="mt-8 max-w-2xl text-lg leading-8 text-[var(--muted)] sm:text-xl sm:leading-9">
            Find trusted local nannies through real video introductions,
            verified credentials and a booking experience designed around your
            family.
          </p>
          <div className="mt-9 flex flex-wrap gap-3">
            <Link className="btn-primary !min-h-14 !px-6" href="/signup?role=parent">
              Find care for my family <ArrowRight size={19} />
            </Link>
            <Link className="btn-secondary !min-h-14 !px-6" href="/signup?role=nanny">
              Join as a nanny
            </Link>
          </div>
          <div className="mt-9 flex flex-wrap gap-x-7 gap-y-3 text-sm font-bold text-[var(--muted)]">
            <span className="flex items-center gap-2">
              <BadgeCheck size={19} className="text-[var(--green)]" />
              Identity checked
            </span>
            <span className="flex items-center gap-2">
              <Play size={18} className="text-[var(--blue-dark)]" />
              Video introductions
            </span>
            <span className="flex items-center gap-2">
              <MapPin size={18} className="text-[var(--coral)]" />
              Distance-based matches
            </span>
          </div>
        </div>

        <div className="rise-delay relative mx-auto w-full max-w-[580px]">
          <div className="absolute -right-20 -top-16 h-48 w-48 rounded-full border-[32px] border-[#cfe9f3]" />
          <div className="absolute -bottom-10 -left-12 h-40 w-40 rounded-full bg-[#f4d0c6]" />
          <div className="relative rotate-[1.5deg] rounded-[52px_52px_120px_52px] bg-[var(--blue-dark)] p-4 shadow-[0_35px_90px_rgba(29,70,95,.22)] sm:p-6">
            <div className="-rotate-[1.5deg] overflow-hidden rounded-[38px_38px_95px_38px] bg-white">
              <div className="relative aspect-[5/4] bg-[linear-gradient(145deg,#d8eef5,#f7fbfc)] p-6 sm:p-9">
                <div className="absolute left-7 top-7 rounded-full bg-white/90 px-4 py-2 text-xs font-extrabold uppercase tracking-[.14em] text-[var(--blue-dark)] shadow-sm">
                  Video introduced
                </div>
                <div className="flex h-full items-center justify-center rounded-[28px] border border-white bg-white/50 text-center backdrop-blur-sm">
                  <div>
                    <span className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-white text-[var(--blue-dark)] shadow-[0_12px_35px_rgba(47,111,146,.18)]">
                      <Play size={34} fill="currentColor" />
                    </span>
                    <p className="mt-5 text-xl font-extrabold">Meet Thandi M.</p>
                    <p className="mt-1 text-[var(--muted)]">A real introduction, before you book</p>
                  </div>
                </div>
              </div>
              <div className="p-6 sm:p-8">
                <div className="flex items-start justify-between gap-5">
                  <div>
                    <h2 className="text-2xl font-extrabold">Thandi M.</h2>
                    <p className="mt-2 flex items-center gap-2 text-[var(--muted)]">
                      <MapPin size={17} /> 3.2 km from your family
                    </p>
                  </div>
                  <span className="pill !bg-[#fff9e9] !text-[var(--ink)]">
                    <Star size={15} fill="#e5aa45" color="#e5aa45" /> 4.9
                  </span>
                </div>
                <div className="mt-6 flex flex-wrap gap-2">
                  <span className="pill">First aid</span>
                  <span className="pill">Background checked</span>
                  <span className="pill">5 years experience</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="border-y border-[#dce9ee] bg-[#eaf6fa] py-8">
        <div className="mx-auto grid max-w-7xl gap-5 px-5 text-center sm:grid-cols-3 sm:px-9">
          {[
            [ShieldCheck, "Reviewed profiles", "People and paperwork checked by our team"],
            [Play, "Meet the real person", "Short videos help trust grow sooner"],
            [CalendarDays, "Care when you need it", "Choose dates, requirements and availability"],
          ].map(([Icon, title, detail]) => (
            <div className="flex items-center justify-center gap-4 px-4 py-2 text-left" key={String(title)}>
              <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-white text-[var(--blue-dark)] shadow-sm">
                <Icon size={22} />
              </span>
              <span>
                <b className="block">{String(title)}</b>
                <span className="mt-1 block text-sm leading-5 text-[var(--muted)]">{String(detail)}</span>
              </span>
            </div>
          ))}
        </div>
      </section>

      <section id="why-my-nanny" className="scroll-mt-8 py-24 sm:py-32">
        <div className="mx-auto max-w-7xl px-5 sm:px-9">
          <div className="grid items-start gap-12 lg:grid-cols-[.8fr_1.2fr]">
            <div className="lg:sticky lg:top-8">
              <div className="eyebrow">Why My Nanny</div>
              <h2 className="display mt-4 text-5xl leading-[.96] sm:text-6xl">
                Trust is built in the details.
              </h2>
              <p className="mt-6 max-w-lg text-lg leading-8 text-[var(--muted)]">
                A profile should tell you more than a name and a rating. My Nanny
                helps families understand the person, the experience and the
                verified information behind every approved caregiver.
              </p>
            </div>
            <div className="grid gap-5 sm:grid-cols-2">
              {[
                [UserRoundCheck, "Know who you are considering", "Approved profiles use a real first name and last initial, with private contact details protected."],
                [Play, "See personality, not just paperwork", "Short video introductions help families understand warmth, communication and confidence."],
                [BadgeCheck, "Verified means reviewed", "A badge is only earned after the related information or document has been approved by an administrator."],
                [MapPin, "Start with who is nearby", "Location and availability narrow the search before ratings and badges provide supporting context."],
              ].map(([Icon, title, detail], index) => (
                <article
                  className={`rounded-[32px] border border-[var(--line)] p-7 shadow-[0_18px_55px_rgba(35,81,105,.07)] ${index === 1 || index === 2 ? "bg-[#fff6f1]" : "bg-white"}`}
                  key={String(title)}
                >
                  <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[var(--blue-pale)] text-[var(--blue-dark)]">
                    <Icon size={23} />
                  </span>
                  <h3 className="mt-6 text-xl font-extrabold">{String(title)}</h3>
                  <p className="mt-3 leading-7 text-[var(--muted)]">{String(detail)}</p>
                </article>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section id="how-it-works" className="scroll-mt-8 bg-[var(--ink)] py-24 text-white sm:py-32">
        <div className="mx-auto max-w-7xl px-5 sm:px-9">
          <div className="grid gap-14 lg:grid-cols-[.85fr_1.15fr]">
            <div>
              <div className="eyebrow !text-[#9ed2e7]">Simple by design</div>
              <h2 className="display mt-4 text-5xl leading-[.95] sm:text-6xl">
                From needing help to feeling supported.
              </h2>
              <p className="mt-6 max-w-lg text-lg leading-8 text-white/65">
                Profiles, matching, booking information and communication stay
                together, so everyone knows what happens next.
              </p>
            </div>
            <ol className="grid gap-4">
              {parentSteps.map((step, index) => (
                <li className="group flex gap-5 rounded-[28px] border border-white/10 bg-white/[.06] p-6 transition hover:bg-white/[.1] sm:p-7" key={step.title}>
                  <span className="display flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-[#9ed2e7] text-2xl text-[var(--ink)]">
                    {index + 1}
                  </span>
                  <span>
                    <b className="block text-xl">{step.title}</b>
                    <span className="mt-2 block leading-7 text-white/60">{step.detail}</span>
                  </span>
                </li>
              ))}
            </ol>
          </div>
          <div className="mt-16 grid overflow-hidden rounded-[36px] bg-[#f5d3ca] text-[var(--ink)] lg:grid-cols-[1fr_auto]">
            <div className="p-8 sm:p-11">
              <div className="flex items-center gap-3 text-sm font-extrabold uppercase tracking-[.16em] text-[#a44e3d]">
                <Sparkles size={18} /> Caregivers
              </div>
              <h3 className="display mt-4 max-w-2xl text-4xl leading-tight sm:text-5xl">
                Your experience deserves to be seen.
              </h3>
              <p className="mt-5 max-w-2xl text-lg leading-8 text-[var(--ink)]/70">
                Build a complete profile, record your introductions and let the
                right families get to know you before the first booking.
              </p>
            </div>
            <div className="flex items-center p-8 pt-0 lg:p-11 lg:pl-0">
              <Link className="btn-primary !min-h-14 !bg-[var(--ink)] !px-6" href="/signup?role=nanny">
                Apply to join <ArrowRight size={19} />
              </Link>
            </div>
          </div>
        </div>
      </section>

      <section className="py-24 sm:py-32">
        <div className="mx-auto max-w-7xl px-5 sm:px-9">
          <div className="mx-auto max-w-3xl text-center">
            <div className="eyebrow">Care with context</div>
            <h2 className="display mt-4 text-5xl leading-[.96] sm:text-6xl">Built for real family life.</h2>
            <p className="mt-6 text-lg leading-8 text-[var(--muted)]">
              The little things matter. My Nanny gives families space to share
              routines, access instructions, food restrictions, medicine needs,
              sleepover expectations and more.
            </p>
          </div>
          <div className="mt-12 grid gap-5 md:grid-cols-3">
            {[
              [Heart, "Family details", "Keep children, routines and household preferences current for easier repeat bookings."],
              [MessageCircle, "Clear communication", "Important booking context and updates are accessible without sharing private details too soon."],
              [Check, "Operational confidence", "Check-in, check-out, availability and booking status help care run more smoothly."],
            ].map(([Icon, title, detail]) => (
              <article className="rounded-[30px] border border-[var(--line)] bg-white p-7" key={String(title)}>
                <Icon className="text-[var(--coral)]" size={27} />
                <h3 className="mt-6 text-xl font-extrabold">{String(title)}</h3>
                <p className="mt-3 leading-7 text-[var(--muted)]">{String(detail)}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-[#edf7fa] py-24 sm:py-28">
        <div className="mx-auto grid max-w-7xl gap-12 px-5 sm:px-9 lg:grid-cols-[.8fr_1.2fr]">
          <div>
            <div className="eyebrow">Good to know</div>
            <h2 className="display mt-4 text-5xl leading-tight">Questions families often ask.</h2>
          </div>
          <div className="grid gap-3">
            {faqs.map((item) => (
              <details className="group rounded-[22px] border border-[#d5e7ee] bg-white p-5 open:shadow-sm" key={item.question}>
                <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-extrabold">
                  {item.question}
                  <span className="text-xl text-[var(--blue-dark)] transition group-open:rotate-45">+</span>
                </summary>
                <p className="mt-4 max-w-2xl leading-7 text-[var(--muted)]">{item.answer}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      <section className="px-5 py-20 sm:px-9 sm:py-28">
        <div className="relative mx-auto max-w-7xl overflow-hidden rounded-[44px] bg-[var(--blue-dark)] px-7 py-14 text-white sm:px-12 sm:py-16 lg:flex lg:items-center lg:justify-between lg:gap-12">
          <div className="absolute -right-16 -top-20 h-64 w-64 rounded-full border-[42px] border-white/10" />
          <div className="relative max-w-3xl">
            <div className="eyebrow !text-[#bde5f3]">Ready when you are</div>
            <h2 className="display mt-4 text-5xl leading-[.95] sm:text-6xl">Let your family meet the right nanny.</h2>
            <p className="mt-5 text-lg leading-8 text-white/70">Create your family profile and start with approved, video-introduced caregivers near you.</p>
          </div>
          <div className="relative mt-8 flex shrink-0 flex-wrap gap-3 lg:mt-0">
            <Link className="btn-secondary !min-h-14 !border-white !px-6" href="/signup?role=parent">
              Create family account <ArrowRight size={19} />
            </Link>
          </div>
        </div>
      </section>

      <footer className="border-t border-[var(--line)] bg-white">
        <div className="mx-auto grid max-w-7xl gap-8 px-5 py-10 sm:px-9 md:grid-cols-[1fr_auto] md:items-end">
          <div>
            <Brand compact />
            <p className="mt-4 max-w-md text-sm leading-6 text-[var(--muted)]">
              Trusted childcare, close to home. Screening, introductions,
              matching and bookings in one thoughtfully designed platform.
            </p>
            <div className="mt-5 flex flex-wrap gap-4 text-sm font-bold text-[var(--muted)]">
              <Link href="/login">Log in</Link>
              <Link href="/signup?role=parent">Parents</Link>
              <Link href="/signup?role=nanny">Nannies</Link>
            </div>
          </div>
          <PoweredByTiqet />
        </div>
      </footer>
    </main>
  );
}
