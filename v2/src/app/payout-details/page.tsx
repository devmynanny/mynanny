"use client";

import { AuthenticatedPage } from "@/components/authenticated-page";
import { apiJson } from "@/lib/api";
import {
  BadgeCheck,
  Landmark,
  LoaderCircle,
  LockKeyhole,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

type Bank = { name: string; code: string; slug?: string | null };
type BankAccount = {
  id: number;
  account_name: string;
  bank_name?: string | null;
  masked_account_number?: string | null;
  is_default: boolean;
  is_verified: boolean;
};
type Banking = { banking_complete: boolean; accounts: BankAccount[] };

export default function PayoutDetailsPage() {
  return (
    <AuthenticatedPage>
      {(role) =>
        role === "nanny" ? (
          <PayoutDetails />
        ) : (
          <div className="card mx-auto max-w-xl p-8 text-center">
            Payout details are available to nanny accounts only.
          </div>
        )
      }
    </AuthenticatedPage>
  );
}

function PayoutDetails() {
  const [banking, setBanking] = useState<Banking | null>(null);
  const [banks, setBanks] = useState<Bank[]>([]);
  const [accountName, setAccountName] = useState("");
  const [bankCode, setBankCode] = useState("");
  const [accountNumber, setAccountNumber] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  async function load() {
    const [bankingData, bankData] = await Promise.all([
      apiJson<Banking>("/nanny/banking"),
      apiJson<{ banks: Bank[] }>("/nanny/banking/banks"),
    ]);
    setBanking(bankingData);
    setBanks(bankData.banks || []);
    setBankCode((current) => current || bankData.banks?.[0]?.code || "");
  }

  useEffect(() => {
    Promise.all([
      apiJson<Banking>("/nanny/banking"),
      apiJson<{ banks: Bank[] }>("/nanny/banking/banks"),
    ])
      .then(([bankingData, bankData]) => {
        setBanking(bankingData);
        setBanks(bankData.banks || []);
        setBankCode(bankData.banks?.[0]?.code || "");
      })
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Unable to load payout details."),
      )
      .finally(() => setLoading(false));
  }, []);

  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const selectedBank = banks.find((bank) => bank.code === bankCode);
    if (!selectedBank) {
      setError("Select a bank.");
      return;
    }
    setSaving(true);
    setError("");
    setStatus("");
    try {
      await apiJson("/nanny/banking", {
        method: "POST",
        body: JSON.stringify({
          account_name: accountName,
          bank_name: selectedBank.name,
          bank_code: selectedBank.code,
          account_number: accountNumber,
        }),
      });
      setAccountNumber("");
      setStatus("Your payout account has been securely linked through Paystack.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save payout details.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-5xl">
      <div className="eyebrow">Nanny earnings</div>
      <h1 className="display mt-2 text-4xl sm:text-5xl">Payout details.</h1>
      <p className="mt-3 max-w-2xl leading-7 text-[var(--muted)]">
        Link the South African bank account where you want to receive your My Nanny earnings.
      </p>

      {loading ? (
        <div className="card mt-8 flex items-center gap-3 p-8 text-[var(--muted)]">
          <LoaderCircle className="animate-spin" /> Loading Paystack banks...
        </div>
      ) : (
        <div className="mt-8 grid gap-6 lg:grid-cols-[.9fr_1.1fr]">
          <div className="grid content-start gap-5">
            <section className={`card p-6 ${banking?.banking_complete ? "bg-emerald-50" : "bg-amber-50"}`}>
              <div className="flex items-start gap-4">
                <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-white text-[var(--green)]">
                  {banking?.banking_complete ? <BadgeCheck /> : <Landmark />}
                </span>
                <div>
                  <h2 className="text-xl font-bold">
                    {banking?.banking_complete ? "Payouts are ready" : "Bank account required"}
                  </h2>
                  <p className="mt-2 leading-7 text-[var(--muted)]">
                    {banking?.banking_complete
                      ? "Paystack can transfer your eligible earnings after each booking’s payout hold."
                      : "You cannot receive payouts until a bank account has been linked."}
                  </p>
                </div>
              </div>
            </section>

            {banking?.accounts.map((account) => (
              <section className="card p-6" key={account.id}>
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <div className="eyebrow">Linked account</div>
                    <h2 className="mt-2 text-xl font-bold">{account.bank_name || "Bank account"}</h2>
                    <p className="mt-1 text-[var(--muted)]">{account.masked_account_number}</p>
                    <p className="mt-1 text-sm text-[var(--muted)]">{account.account_name}</p>
                  </div>
                  <span className="pill">{account.is_verified ? "Paystack linked" : "Pending"}</span>
                </div>
              </section>
            ))}

            <section className="card p-6">
              <div className="flex gap-3">
                <ShieldCheck className="shrink-0 text-[var(--green)]" />
                <div>
                  <h2 className="font-bold">Handled securely by Paystack</h2>
                  <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
                    My Nanny keeps a masked account reference for display and the Paystack recipient code used for transfers. Your full account number is not displayed after setup.
                  </p>
                </div>
              </div>
            </section>
          </div>

          <form className="card p-6 sm:p-8" onSubmit={save}>
            <div className="flex items-center gap-3">
              <LockKeyhole className="text-[var(--blue-dark)]" />
              <div>
                <div className="eyebrow">Secure setup</div>
                <h2 className="mt-1 text-2xl font-bold">
                  {banking?.banking_complete ? "Link another account" : "Link your bank account"}
                </h2>
              </div>
            </div>
            <div className="mt-7 grid gap-5">
              <label>
                <span className="mb-2 block text-sm font-bold">Account holder</span>
                <input className="field" value={accountName} onChange={(event) => setAccountName(event.target.value)} autoComplete="name" placeholder="Name as shown on the account" required />
              </label>
              <label>
                <span className="mb-2 block text-sm font-bold">Bank</span>
                <select className="field" value={bankCode} onChange={(event) => setBankCode(event.target.value)} required>
                  {!banks.length && <option value="">No banks available</option>}
                  {banks.map((bank) => <option value={bank.code} key={bank.code}>{bank.name}</option>)}
                </select>
              </label>
              <label>
                <span className="mb-2 block text-sm font-bold">Account number</span>
                <input className="field" value={accountNumber} onChange={(event) => setAccountNumber(event.target.value.replace(/\D/g, ""))} inputMode="numeric" autoComplete="off" placeholder="Enter numbers only" minLength={6} required />
                <span className="mt-2 block text-xs leading-5 text-[var(--muted)]">Please check this carefully. Payouts will be sent to the account linked by Paystack.</span>
              </label>
            </div>
            {error && <div className="mt-5 rounded-2xl bg-red-50 p-4 text-sm text-red-700" role="alert">{error}</div>}
            {status && <div className="mt-5 rounded-2xl bg-emerald-50 p-4 text-sm text-emerald-800" role="status">{status}</div>}
            <button className="btn-primary mt-6 w-full" disabled={saving || !banks.length} type="submit">
              {saving ? <LoaderCircle className="animate-spin" size={18} /> : <ShieldCheck size={18} />}
              {saving ? "Linking securely..." : "Link account with Paystack"}
            </button>
            <Link href="/dashboard" className="btn-quiet mt-3 w-full">Return home</Link>
          </form>
        </div>
      )}
    </div>
  );
}
