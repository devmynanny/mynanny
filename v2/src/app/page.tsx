import { Brand } from "@/components/brand";
import { ArrowRight, BadgeCheck, MapPin, PlayCircle, Star } from "lucide-react";
import Link from "next/link";

export default function Home() {
  return (
    <main className="overflow-hidden">
      <header className="mx-auto flex h-24 w-full max-w-7xl items-center justify-between px-5 sm:px-8">
        <Brand />
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
              Video screened
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
      <section id="how-it-works" className="bg-[var(--ink)] py-16 text-white">
        <div className="mx-auto grid max-w-7xl gap-8 px-5 sm:px-8 md:grid-cols-3">
          {[
            [
              "01",
              "Tell us what you need",
              "Choose your dates, location and the kind of support your family needs.",
            ],
            [
              "02",
              "Meet screened nannies",
              "Watch video introductions and compare verified experience and reviews.",
            ],
            [
              "03",
              "Book with confidence",
              "Send your request and manage every booking in one calm place.",
            ],
          ].map(([n, t, b]) => (
            <div key={n}>
              <div className="text-sm font-extrabold text-[#9ed2e7]">{n}</div>
              <h2 className="mt-3 text-xl font-bold">{t}</h2>
              <p className="mt-3 leading-7 text-white/65">{b}</p>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
