import { Brand } from "@/components/brand";
import { PoweredByTiqet } from "@/components/powered-by-tiqet";
import {
  ArrowRight,
  BadgeCheck,
  CalendarDays,
  ExternalLink,
  Heart,
  Mail,
  MapPin,
  MessageCircle,
  Play,
  ShieldCheck,
  Sparkles,
  Star,
  UserRoundCheck,
} from "lucide-react";
import Image from "next/image";
import Link from "next/link";

function GoogleLogo() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="h-10 w-10">
      <path fill="#4285F4" d="M21.6 12.23c0-.71-.06-1.4-.18-2.05H12v3.87h5.38a4.6 4.6 0 0 1-2 3.02v2.51h3.24c1.9-1.75 2.98-4.33 2.98-7.35Z" />
      <path fill="#34A853" d="M12 22c2.7 0 4.97-.9 6.62-2.42l-3.24-2.51c-.9.6-2.05.96-3.38.96-2.6 0-4.8-1.76-5.59-4.12H3.07v2.59A10 10 0 0 0 12 22Z" />
      <path fill="#FBBC05" d="M6.41 13.91A6.02 6.02 0 0 1 6.1 12c0-.66.11-1.3.31-1.91V7.5H3.07A10 10 0 0 0 2 12c0 1.61.39 3.14 1.07 4.5l3.34-2.59Z" />
      <path fill="#EA4335" d="M12 5.97c1.47 0 2.79.5 3.83 1.5l2.87-2.88A9.62 9.62 0 0 0 12 2a10 10 0 0 0-8.93 5.5l3.34 2.59C7.2 7.73 9.4 5.97 12 5.97Z" />
    </svg>
  );
}

function FacebookLogo() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="h-11 w-11">
      <circle cx="12" cy="12" r="11" fill="#1877F2" />
      <path fill="white" d="M13.7 21v-8h2.7l.4-3.1h-3.1v-2c0-.9.25-1.5 1.57-1.5h1.68V3.63a22.7 22.7 0 0 0-2.45-.13c-2.43 0-4.1 1.48-4.1 4.2v2.2H7.65V13h2.75v8h3.3Z" />
    </svg>
  );
}

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
    question: "Can a nanny work after 17:00?",
    answer:
      "Yes. Evening care is available. When a nanny relies on public transport, the family may need to arrange safe transport after the applicable evening cut-off.",
  },
  {
    question: "Can a nanny give medication?",
    answer:
      "Parents should administer medication where possible. If that is not possible, the booking must include clear written instructions and the required consent.",
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
          <div className="eyebrow mb-5">Welcome to My Nanny</div>
          <h1 className="display max-w-[760px] text-[clamp(3.4rem,7vw,7rem)] leading-[.88] text-[var(--ink)]">
            Care that feels like family.
          </h1>
          <p className="mt-8 max-w-2xl text-lg leading-8 text-[var(--muted)] sm:text-xl sm:leading-9">
            Reliable childcare when you need it most. Find trusted local
            nannies through real video introductions, verified credentials and
            a booking experience designed around your family.
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
              <div className="relative aspect-[5/4] overflow-hidden bg-[#d8eef5] p-5 sm:p-7">
                <Image
                  alt="Illustration of a nanny feeding a happy baby"
                  className="object-cover"
                  fill
                  priority
                  sizes="(min-width: 1024px) 42vw, 100vw"
                  src="/hero-nanny-feeding-v2.png"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-[#173650]/35 via-transparent to-white/10" />
                <div className="absolute left-7 top-7 rounded-full bg-white/90 px-4 py-2 text-xs font-extrabold uppercase tracking-[.14em] text-[var(--blue-dark)] shadow-sm backdrop-blur-sm">
                  Video introduced
                </div>
                <div className="relative flex h-full items-end justify-center rounded-[28px] border border-white/70 p-1 text-center">
                  <div className="flex w-full items-center gap-3 rounded-[20px] bg-white/90 px-4 py-3 text-left shadow-[0_14px_40px_rgba(23,54,80,.18)] backdrop-blur-sm sm:gap-4 sm:rounded-[24px] sm:px-5 sm:py-4">
                    <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-[var(--blue-dark)] text-white shadow-[0_10px_28px_rgba(23,54,80,.2)] sm:h-14 sm:w-14">
                      <Play size={20} fill="currentColor" className="sm:h-6 sm:w-6" />
                    </span>
                    <div>
                      <p className="text-base font-extrabold sm:text-lg">Meet Veronica M.</p>
                      <p className="mt-0.5 text-xs text-[var(--muted)] sm:mt-1 sm:text-base">A real introduction, before you book</p>
                    </div>
                  </div>
                </div>
              </div>
              <div className="p-6 sm:p-8">
                <div className="flex items-start justify-between gap-5">
                  <div>
                    <h2 className="text-2xl font-extrabold">Veronica M.</h2>
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
              <div className="eyebrow">The My Nanny difference</div>
              <h2 className="display mt-4 text-5xl leading-[.96] sm:text-6xl">
                A helping hand who truly gets it.
              </h2>
              <p className="mt-6 max-w-lg text-lg leading-8 text-[var(--muted)]">
                My Nanny was founded by Mariette Diener, a mother who understood
                that choosing someone to care for your child is deeply personal.
                Built around family and Kingdom Values, the platform helps you
                understand the person, experience and verified information behind
                every approved caregiver.
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
          <div className="grid items-center gap-14 lg:grid-cols-[.78fr_1.22fr]">
            <div>
              <div className="eyebrow !text-[#9ed2e7]">How does it work?</div>
              <h2 className="display mt-4 text-5xl leading-[.95] sm:text-6xl">
                From needing help to feeling supported.
              </h2>
              <p className="mt-6 max-w-lg text-lg leading-8 text-white/65">
                No monthly fee. My Nanny is a flexible, pay-as-you-go service,
                with pricing shown before you choose a caregiver. Profiles,
                matching, bookings and communication stay together so everyone
                knows what happens next.
              </p>
            </div>
            <div className="rounded-[38px] border border-white/10 bg-white/[.06] p-4 shadow-[0_30px_80px_rgba(0,0,0,.2)] sm:p-6">
              <div className="overflow-hidden rounded-[30px] bg-[#f8fcfd] text-[var(--ink)]">
                <div className="border-b border-[var(--line)] p-5 sm:p-6">
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <p className="eyebrow">1 · Choose your dates</p>
                      <h3 className="mt-2 text-xl font-extrabold">August 2026</h3>
                    </div>
                    <span className="pill !bg-[#dff3ea] !text-[#2e725d]">
                      <CalendarDays size={16} /> 2 days selected
                    </span>
                  </div>
                  <div className="mt-5 grid grid-cols-7 gap-2 text-center text-sm">
                    {[
                      ["S", "9", false],
                      ["M", "10", true],
                      ["T", "11", true],
                      ["W", "12", false],
                      ["T", "13", false],
                      ["F", "14", false],
                      ["S", "15", false],
                    ].map(([day, date, selected]) => (
                      <div key={String(date)}>
                        <span className="block text-xs font-extrabold text-[var(--muted)]">{String(day)}</span>
                        <span
                          className={`mt-2 flex aspect-square items-center justify-center rounded-2xl font-extrabold ${selected ? "bg-[var(--blue-dark)] text-white shadow-md" : "bg-white"}`}
                        >
                          {String(date)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="p-5 sm:p-6">
                  <p className="eyebrow">2 · Meet an available nanny</p>
                  <div className="mt-4 flex flex-col gap-5 rounded-[26px] border border-[var(--line)] bg-white p-5 sm:flex-row sm:items-center">
                    <span className="flex h-16 w-16 shrink-0 items-center justify-center rounded-[22px] bg-[var(--blue-pale)] text-[var(--blue-dark)]">
                      <UserRoundCheck size={30} />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <h3 className="text-xl font-extrabold">Veronica M.</h3>
                        <span className="pill !bg-[#fff9e9]">
                          <Star size={14} fill="#e5aa45" color="#e5aa45" /> 4.9
                        </span>
                      </div>
                      <p className="mt-2 flex items-center gap-2 text-sm text-[var(--muted)]">
                        <MapPin size={16} /> 3.2 km away
                      </p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <span className="pill"><Play size={14} /> Video introduced</span>
                        <span className="pill"><BadgeCheck size={14} /> Approved</span>
                      </div>
                    </div>
                  </div>
                  <div className="mt-4 flex items-center justify-between gap-4 rounded-[22px] bg-[#eaf6fa] px-5 py-4">
                    <div>
                      <p className="text-xs font-extrabold uppercase tracking-[.14em] text-[var(--blue-dark)]">3 · Request care</p>
                      <p className="mt-1 text-sm text-[var(--muted)]">Dates and nanny stay together.</p>
                    </div>
                    <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-[var(--blue-dark)] text-white">
                      <ArrowRight size={20} />
                    </span>
                  </div>
                </div>
              </div>
            </div>
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
            <div className="eyebrow">What makes our nannies exceptional?</div>
            <h2 className="display mt-4 text-5xl leading-[.96] sm:text-6xl">Carefully screened. Ready for real family life.</h2>
            <p className="mt-6 text-lg leading-8 text-[var(--muted)]">
              Every visible nanny has completed a video introduction and team
              review. Approved badges make training, identity, background and
              experience easier to understand, while booking details cover the
              routines and little things that matter in your home.
            </p>
          </div>
          <div className="mt-12 grid gap-5 md:grid-cols-3">
            {[
              [ShieldCheck, "Vetted and reviewed", "Identity, supporting documents, references and trust badges are reviewed by the My Nanny team."],
              [Heart, "Prepared for your family", "Share children’s routines, household preferences, food restrictions and care expectations before the booking."],
              [MessageCircle, "Clear communication", "Booking updates and important context stay together without exposing private contact details too soon."],
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

      <section className="border-y border-[var(--line)] bg-[#fff7f3] py-24 sm:py-28">
        <div className="mx-auto max-w-7xl px-5 sm:px-9">
          <div className="mx-auto max-w-3xl text-center">
            <div className="eyebrow">What our clients have to say</div>
            <h2 className="display mt-4 text-5xl leading-[.96] sm:text-6xl">
              Trusted by families beyond the platform.
            </h2>
            <p className="mt-6 text-lg leading-8 text-[var(--muted)]">
              Read independent feedback from families who have used My Nanny
              for the moments when reliable care matters most.
            </p>
          </div>
          <div className="mx-auto mt-12 grid max-w-4xl gap-5 md:grid-cols-2">
            <a
              className="group flex min-h-56 items-center gap-6 rounded-[34px] border border-[var(--line)] bg-white p-7 shadow-[0_18px_55px_rgba(35,81,105,.07)] transition hover:-translate-y-1 hover:shadow-[0_24px_65px_rgba(35,81,105,.12)] sm:p-9"
              href="https://g.page/r/CfJHxxMZ_CGGEBE/review"
              rel="noreferrer"
              target="_blank"
            >
              <span className="flex h-20 w-20 shrink-0 items-center justify-center rounded-[26px] bg-white shadow-[inset_0_0_0_1px_#e5e7eb]">
                <GoogleLogo />
              </span>
              <span>
                <span className="block text-2xl font-extrabold">Google reviews</span>
                <span className="mt-2 block leading-7 text-[var(--muted)]">Read feedback or share your My Nanny experience.</span>
                <span className="mt-5 flex items-center gap-2 text-sm font-extrabold text-[var(--blue-dark)]">
                  View on Google <ExternalLink size={16} />
                </span>
              </span>
            </a>
            <a
              className="group flex min-h-56 items-center gap-6 rounded-[34px] border border-[var(--line)] bg-white p-7 shadow-[0_18px_55px_rgba(35,81,105,.07)] transition hover:-translate-y-1 hover:shadow-[0_24px_65px_rgba(35,81,105,.12)] sm:p-9"
              href="https://www.facebook.com/MyNannySA/"
              rel="noreferrer"
              target="_blank"
            >
              <span className="flex h-20 w-20 shrink-0 items-center justify-center rounded-[26px] bg-[#eef5ff]">
                <FacebookLogo />
              </span>
              <span>
                <span className="block text-2xl font-extrabold">Facebook reviews</span>
                <span className="mt-2 block leading-7 text-[var(--muted)]">Visit our community page and see what families are saying.</span>
                <span className="mt-5 flex items-center gap-2 text-sm font-extrabold text-[var(--blue-dark)]">
                  View on Facebook <ExternalLink size={16} />
                </span>
              </span>
            </a>
          </div>
        </div>
      </section>

      <section className="bg-[#edf7fa] py-24 sm:py-28">
        <div className="mx-auto grid max-w-7xl gap-12 px-5 sm:px-9 lg:grid-cols-[.8fr_1.2fr]">
          <div>
            <div className="eyebrow">Frequently asked questions</div>
            <h2 className="display mt-4 text-5xl leading-tight">Good to know before you book.</h2>
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

      <section id="contact" className="scroll-mt-8 px-5 py-20 sm:px-9 sm:py-24">
        <div className="mx-auto grid max-w-7xl overflow-hidden rounded-[42px] border border-[var(--line)] bg-white shadow-[0_24px_70px_rgba(35,81,105,.08)] lg:grid-cols-[1.15fr_.85fr]">
          <div className="p-8 sm:p-12">
            <div className="eyebrow">Contact us</div>
            <h2 className="display mt-4 max-w-2xl text-5xl leading-[.96] sm:text-6xl">
              Need a little help before you begin?
            </h2>
            <p className="mt-6 max-w-2xl text-lg leading-8 text-[var(--muted)]">
              Whether you are looking for care or applying as a nanny, our team
              can help you understand the next step.
            </p>
          </div>
          <div className="flex flex-col justify-center bg-[var(--blue-pale)] p-8 sm:p-12">
            <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-white text-[var(--blue-dark)] shadow-sm">
              <Mail size={25} />
            </span>
            <p className="mt-6 text-sm font-extrabold uppercase tracking-[.15em] text-[var(--blue-dark)]">Email the My Nanny team</p>
            <a className="mt-2 break-all text-2xl font-extrabold text-[var(--ink)] sm:text-3xl" href="mailto:sayhi@mynanny.co.za">
              sayhi@mynanny.co.za
            </a>
            <a className="btn-primary mt-7 w-fit !min-h-14 !px-6" href="mailto:sayhi@mynanny.co.za?subject=My%20Nanny%20enquiry">
              Send an enquiry <ArrowRight size={19} />
            </a>
          </div>
        </div>
      </section>

      <section className="px-5 py-20 sm:px-9 sm:py-28">
        <div className="relative mx-auto max-w-7xl overflow-hidden rounded-[44px] bg-[var(--blue-dark)] px-7 py-14 text-white sm:px-12 sm:py-16 lg:flex lg:items-center lg:justify-between lg:gap-12">
          <div className="absolute -right-16 -top-20 h-64 w-64 rounded-full border-[42px] border-white/10" />
          <div className="relative max-w-3xl">
            <div className="eyebrow !text-[#bde5f3]">Ready to book?</div>
            <h2 className="display mt-4 text-5xl leading-[.95] sm:text-6xl">Experience the My Nanny difference.</h2>
            <p className="mt-5 text-lg leading-8 text-white/70">Create your family profile and meet approved, video-introduced caregivers near you.</p>
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
              <Link href="#contact">Contact us</Link>
              <a href="https://g.page/r/CfJHxxMZ_CGGEBE/review" rel="noreferrer" target="_blank">Google reviews</a>
              <a href="https://www.facebook.com/MyNannySA/" rel="noreferrer" target="_blank">Facebook</a>
            </div>
          </div>
          <PoweredByTiqet />
        </div>
      </footer>
    </main>
  );
}
