import { Brand } from "@/components/brand";
import {
  ArrowRight,
  BadgeCheck,
  MapPin,
  PlayCircle,
  ShieldCheck,
  Star,
} from "lucide-react";
import Link from "next/link";

export default function Home() {
  return (
    <main className="overflow-hidden">
      <header className="mx-auto flex h-28 w-full max-w-7xl items-center justify-between px-5 sm:h-36 sm:px-8">
        <Brand home />
        <div className="flex items-center gap-2">
          <Link className="btn-quiet desktop-only" href="#how-it-works">
            How it works
          </Link>
          <Link className="btn-secondary" href="/login">
            Log in
          </Link>
        </div>
      </header>
      <section className="mx-auto grid min-h-[650px] max-w-7xl items-center gap-12 px-5 pb-20 pt-10 sm:px-8 lg:grid-cols-[1.06fr_.94fr] lg:pt-6">
        <div className="rise max-w-2xl">
          <div className="eyebrow mb-5">Trusted childcare, close to home</div>
          <h1 className="display text-5xl leading-[.98] text-[var(--ink)] sm:text-7xl">
            The right nanny feels like part of the family.
          </h1>
          <p className="mt-7 max-w-xl text-lg leading-8 text-[var(--muted)]">
            Meet carefully screened nannies through real video introductions,
            verified credentials and genuine family reviews.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link className="btn-primary" href="/signup?role=parent">
              Find a nanny <ArrowRight size={18} />
            </Link>
            <Link className="btn-secondary" href="/signup?role=nanny">
              I’m a nanny
            </Link>
          </div>
          <div className="mt-8 flex flex-wrap gap-x-6 gap-y-3 text-sm font-bold text-[var(--muted)]">
            <span className="flex items-center gap-2">
              <BadgeCheck size={18} className="text-[var(--green)]" />
              Identity checked
            </span>
            <span className="flex items-center gap-2">
              <PlayCircle size={18} className="text-[var(--blue-dark)]" />
              Video Introductions
            </span>
            <span className="flex items-center gap-2">
              <MapPin size={18} className="text-[var(--coral)]" />
              Local matches
            </span>
          </div>
        </div>
        <div className="rise-delay relative mx-auto w-full max-w-lg">
          <div className="absolute -left-8 -top-8 h-36 w-36 rounded-full bg-[#d6edf6]" />
          <div className="relative rounded-[36px] bg-[var(--blue-dark)] p-5 shadow-[0_30px_80px_rgba(32,79,105,.25)] sm:p-7">
            <div className="rounded-[26px] bg-white p-4 sm:p-5">
              <div className="aspect-[4/3] overflow-hidden rounded-[20px] bg-[linear-gradient(145deg,#c5e6f2,#edf8fb)] p-6">
                <div className="flex h-full items-center justify-center rounded-[16px] border border-white/70 bg-white/45 text-center">
                  <div>
                    <PlayCircle className="mx-auto h-16 w-16 text-[var(--blue-dark)]" />
                    <div className="mt-3 font-bold">Meet Thandi M.</div>
                    <div className="mt-1 text-sm text-[var(--muted)]">
                      Watch her introduction
                    </div>
                  </div>
                </div>
              </div>
              <div className="mt-5 flex items-center justify-between gap-4">
                <div>
                  <div className="text-lg font-extrabold">Thandi M.</div>
                  <div className="mt-1 flex items-center gap-1 text-sm text-[var(--muted)]">
                    <MapPin size={14} /> 3.2 km away
                  </div>
                </div>
                <div className="pill">
                  <Star size={14} fill="#e5aa45" color="#e5aa45" /> 4.9
                </div>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <span className="pill">First aid</span>
                <span className="pill">Background checked</span>
                <span className="pill">5 years experience</span>
              </div>
            </div>
          </div>
        </div>
      </section>
      <section
        id="how-it-works"
        className="scroll-mt-6 bg-[var(--ink)] py-20 text-white"
      >
        <div className="mx-auto max-w-7xl px-5 sm:px-8">
          <div className="max-w-3xl">
            <div className="eyebrow !text-[#9ed2e7]">How My Nanny works</div>
            <h2 className="display mt-3 text-4xl leading-tight sm:text-6xl">
              From “we need help” to care you can feel good about.
            </h2>
            <p className="mt-5 max-w-2xl text-lg leading-8 text-white/65">
              My Nanny brings screening, matching, bookings and communication
              together, so families and nannies both know what happens next.
            </p>
          </div>

          <div className="mt-12 grid gap-6 lg:grid-cols-2">
            <article className="rounded-[32px] bg-white p-6 text-[var(--ink)] sm:p-8">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <div className="eyebrow">For parents</div>
                  <h3 className="mt-2 text-2xl font-bold">
                    Find and book the right support
                  </h3>
                </div>
                <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[var(--blue-pale)] text-xl font-bold text-[var(--blue-dark)]">
                  P
                </span>
              </div>
              <ol className="mt-7 grid gap-3">
                {[
                  [
                    "1",
                    "Tell us about your family",
                    "Complete your care needs, children’s details, home location and access information once.",
                  ],
                  [
                    "2",
                    "Choose dates and requirements",
                    "Add the times, responsibilities and any sleepover, medicine or transport expectations.",
                  ],
                  [
                    "3",
                    "View available nannies",
                    "See approved, video-introduced nannies who match the location, dates and availability you selected.",
                  ],
                  [
                    "4",
                    "Request and manage the booking",
                    "Choose your nanny, send the request and keep booking details and communication together.",
                  ],
                ].map(([number, title, detail]) => (
                  <li
                    className="flex gap-4 rounded-2xl bg-[var(--canvas)] p-4"
                    key={number}
                  >
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[var(--blue-dark)] text-sm font-bold text-white">
                      {number}
                    </span>
                    <span>
                      <b className="block">{title}</b>
                      <span className="mt-1 block text-sm leading-6 text-[var(--muted)]">
                        {detail}
                      </span>
                    </span>
                  </li>
                ))}
              </ol>
              <p className="mt-5 flex items-start gap-2 text-sm leading-6 text-[var(--muted)]">
                <ShieldCheck className="mt-0.5 shrink-0 text-[var(--green)]" size={18} />
                Paystack handles payment authorisation securely. My Nanny does
                not store your full card details.
              </p>
            </article>

            <article className="rounded-[32px] border border-white/15 bg-white/[.07] p-6 sm:p-8">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <div className="eyebrow !text-[#9ed2e7]">For nannies</div>
                  <h3 className="mt-2 text-2xl font-bold">
                    Build trust before the first booking
                  </h3>
                </div>
                <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white/10 text-xl font-bold text-[#9ed2e7]">
                  N
                </span>
              </div>
              <ol className="mt-7 grid gap-3">
                {[
                  [
                    "1",
                    "Create your complete profile",
                    "Add your experience, location, availability and required identity and eligibility information.",
                  ],
                  [
                    "2",
                    "Record your video introductions",
                    "Answer four short questions so families can get a genuine sense of who you are.",
                  ],
                  [
                    "3",
                    "Complete My Nanny review",
                    "Our team reviews your profile, documents and introductions before parents can discover you.",
                  ],
                  [
                    "4",
                    "Receive requests and earnings",
                    "Set your availability, respond to suitable bookings and receive eligible payouts through Paystack.",
                  ],
                ].map(([number, title, detail]) => (
                  <li
                    className="flex gap-4 rounded-2xl border border-white/10 bg-white/[.05] p-4"
                    key={number}
                  >
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#9ed2e7] text-sm font-bold text-[var(--ink)]">
                      {number}
                    </span>
                    <span>
                      <b className="block">{title}</b>
                      <span className="mt-1 block text-sm leading-6 text-white/60">
                        {detail}
                      </span>
                    </span>
                  </li>
                ))}
              </ol>
              <p className="mt-5 flex items-start gap-2 text-sm leading-6 text-white/60">
                <BadgeCheck className="mt-0.5 shrink-0 text-[#9ed2e7]" size={18} />
                Parents only see approved profiles with completed video
                introductions. Contact details remain private.
              </p>
            </article>
          </div>

          <div className="mt-8 flex flex-col items-start justify-between gap-5 rounded-[28px] bg-[#9ed2e7] p-6 text-[var(--ink)] sm:flex-row sm:items-center sm:p-8">
            <div>
              <h3 className="text-xl font-bold">Ready to take the next step?</h3>
              <p className="mt-1 text-sm text-[var(--ink)]/65">
                Start as a family looking for care or apply to join My Nanny.
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Link className="btn-primary" href="/signup?role=parent">
                Find a nanny <ArrowRight size={18} />
              </Link>
              <Link className="btn-secondary !border-white/70 !bg-white" href="/signup?role=nanny">
                I’m a nanny
              </Link>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
