"use client";

import { Brand } from "@/components/brand";
import { PoweredByTiqet } from "@/components/powered-by-tiqet";
import { apiJson } from "@/lib/api";
import {
  ArrowRight,
  CheckCircle2,
  Eye,
  EyeOff,
  Lock,
  Mail,
} from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

type Me = { name: string; role: string; is_admin?: boolean };
function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const nextPath = params.get("next") === "/placements" ? "/placements" : "/dashboard";
  const isPermanentJourney = nextPath === "/placements";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    apiJson<Me>("/auth/me")
      .then(() => router.replace(nextPath))
      .catch(() => undefined);
  }, [nextPath, router]);
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      await apiJson("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      router.push(nextPath);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "We couldn't sign you in. Please check your details.",
      );
      setLoading(false);
    }
  }
  return (
    <main className="grid min-h-screen lg:grid-cols-[.9fr_1.1fr]">
      <section className="relative hidden overflow-hidden bg-[var(--blue-dark)] p-12 text-white lg:flex lg:flex-col">
        <div className="absolute -right-24 -top-24 h-80 w-80 rounded-full border-[70px] border-white/5" />
        <div className="relative self-start rounded-[24px] bg-white px-5 py-3 shadow-sm">
          <Brand large />
        </div>
        <div className="relative my-auto max-w-lg">
          <div className="eyebrow !text-[#bfe5f3]">Welcome back</div>
          <h1 className="display mt-5 text-6xl leading-[1.02]">
            {isPermanentJourney
              ? "Your permanent search continues here."
              : "Care your family can feel good about."}
          </h1>
          <p className="mt-6 text-lg leading-8 text-white/70">
            {isPermanentJourney
              ? "Sign in to choose Self-Match or Concierge and manage your search, interviews and offers."
              : "Your trusted nannies, bookings and conversations are waiting for you."}
          </p>
          <div className="mt-9 grid gap-4 text-sm font-bold text-white/80">
            {[
              "Every visible nanny is video screened",
              "Credentials and trust badges are verified",
              "Bookings stay organised in one place",
            ].map((item) => (
              <div key={item} className="flex items-center gap-3">
                <CheckCircle2 size={19} className="text-[#bfe5f3]" />
                {item}
              </div>
            ))}
          </div>
        </div>
        <PoweredByTiqet className="relative" />
      </section>
      <section className="flex items-center justify-center px-5 py-10 sm:px-10">
        <div className="w-full max-w-md rise">
          <div className="mb-10 lg:hidden">
            <Brand />
          </div>
          <div className="eyebrow">Sign in</div>
          <h2 className="display mt-3 text-4xl">Good to see you again.</h2>
          <p className="mt-3 text-[var(--muted)]">
            Use the email and password linked to your account.
          </p>
          <form onSubmit={submit} className="mt-8 grid gap-5">
            <label>
              <span className="mb-2 block text-sm font-bold">
                Email address
              </span>
              <span className="relative block">
                <Mail
                  className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400"
                  size={18}
                />
                <input
                  className="field !pl-11"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                />
              </span>
            </label>
            <label>
              <span className="mb-2 flex items-center justify-between text-sm font-bold">
                <span>Password</span>
                <button
                  type="button"
                  className="text-xs text-[var(--blue-dark)]"
                >
                  Forgot password?
                </button>
              </span>
              <span className="relative block">
                <Lock
                  className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400"
                  size={18}
                />
                <input
                  className="field !px-11"
                  type={show ? "text" : "password"}
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Your password"
                />
                <button
                  type="button"
                  aria-label={show ? "Hide password" : "Show password"}
                  onClick={() => setShow(!show)}
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400"
                >
                  {show ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </span>
            </label>
            {error && (
              <div
                role="alert"
                className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700"
              >
                {error}
              </div>
            )}
            <button className="btn-primary w-full" disabled={loading}>
              {loading ? "Signing in..." : "Sign in"}
              <ArrowRight size={18} />
            </button>
          </form>
          <p className="mt-7 text-center text-sm text-[var(--muted)]">
            New to My Nanny?{" "}
            <Link href={isPermanentJourney ? "/signup?role=parent&next=%2Fplacements" : "/signup"} className="font-bold text-[var(--blue-dark)]">
              Create an account
            </Link>
          </p>
          <div className="mt-10 flex justify-center lg:hidden">
            <PoweredByTiqet />
          </div>
        </div>
      </section>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<main className="min-h-screen" />}>
      <LoginForm />
    </Suspense>
  );
}
