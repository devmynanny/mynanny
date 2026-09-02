"use client";

import { Brand } from "@/components/brand";
import type { GoogleAddress } from "@/components/google-address-input";
import { NannyLocationConfirmation } from "@/components/nanny-location-confirmation";
import { PoweredByTiqet } from "@/components/powered-by-tiqet";
import { apiJson } from "@/lib/api";
import {
  ArrowLeft,
  ArrowRight,
  BadgeCheck,
  MapPin,
  UserRound,
} from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

type Role = "parent" | "nanny";
type FormState = {
  name: string;
  email: string;
  password: string;
  phone: string;
  phoneAlt: string;
  nationality: string;
  gender: string;
  ethnicity: string;
  saIdNumber: string;
  passportNumber: string;
  passportExpiry: string;
  permitStatus: string;
  workPermitExpiry: string;
  hasOwnCar: string;
  hasDriversLicense: string;
  jobType: string;
  policeClearanceStatus: string;
  hasOwnKids: string;
  ownKidsDetails: string;
  medicalConditions: string;
  trainingStatus: string;
};

const initialForm: FormState = {
  name: "",
  email: "",
  password: "",
  phone: "",
  phoneAlt: "",
  nationality: "South African",
  gender: "",
  ethnicity: "",
  saIdNumber: "",
  passportNumber: "",
  passportExpiry: "",
  permitStatus: "",
  workPermitExpiry: "",
  hasOwnCar: "",
  hasDriversLicense: "",
  jobType: "",
  policeClearanceStatus: "",
  hasOwnKids: "",
  ownKidsDetails: "",
  medicalConditions: "",
  trainingStatus: "",
};

const boolValue = (value: string) =>
  value === "yes" ? true : value === "no" ? false : null;

function SignupForm() {
  const router = useRouter();
  const params = useSearchParams();
  const nextPath = params.get("next") === "/placements" ? "/placements" : "/dashboard";
  const [role, setRole] = useState<Role>(
    params.get("role") === "nanny" ? "nanny" : "parent",
  );
  const [form, setForm] = useState(initialForm);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [accountCreated, setAccountCreated] = useState(false);
  const [selectedAddress, setSelectedAddress] =
    useState<GoogleAddress | null>(null);
  const isSouthAfrican =
    form.nationality.trim().toLowerCase() === "south african";
  const isPermanentParent = role === "parent" && nextPath === "/placements";

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function chooseRole(nextRole: Role) {
    setRole(nextRole);
    const nextQuery = nextPath === "/placements" ? "&next=%2Fplacements" : "";
    window.history.replaceState(null, "", `/signup?role=${nextRole}${nextQuery}`);
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    if (accountCreated && isSouthAfrican && !/^\d{13}$/.test(form.saIdNumber)) {
      setError("Your South African ID number must contain 13 digits.");
      return;
    }
    setLoading(true);
    try {
      if (!accountCreated) {
        await apiJson("/auth/signup", {
          method: "POST",
          body: JSON.stringify({
            name: form.name,
            email: form.email,
            password: form.password,
            role,
            phone: form.phone || null,
          }),
        });
        if (role === "parent") {
          router.push(nextPath);
          router.refresh();
          return;
        }
        setAccountCreated(true);
        setLoading(false);
        window.scrollTo({ top: 0, behavior: "smooth" });
        return;
      }

      await apiJson("/nannies/me/profile", {
        method: "PATCH",
        body: JSON.stringify({
          phone: form.phone || null,
          phone_alt: form.phoneAlt || null,
          nationality: form.nationality,
          gender: form.gender,
          ethnicity: form.ethnicity,
          sa_id_number: isSouthAfrican ? form.saIdNumber : null,
          passport_number: isSouthAfrican ? null : form.passportNumber,
          passport_expiry: isSouthAfrican ? null : form.passportExpiry,
          permit_status: isSouthAfrican ? null : form.permitStatus,
          work_permit: form.permitStatus === "permit",
          waiver: form.permitStatus === "waiver",
          work_permit_expiry: form.workPermitExpiry || null,
          has_own_car: boolValue(form.hasOwnCar),
          has_drivers_license: boolValue(form.hasDriversLicense),
          job_type: form.jobType,
          police_clearance_status: form.policeClearanceStatus,
          has_own_kids: boolValue(form.hasOwnKids),
          own_kids_details: form.ownKidsDetails || null,
          medical_conditions: form.medicalConditions || null,
          my_nanny_training_status: form.trainingStatus,
        }),
      });
      if (!selectedAddress) {
        throw new Error(
          "Use GPS and confirm the address where you live before continuing.",
        );
      }
      await apiJson("/nannies/me/location", {
        method: "PATCH",
        body: JSON.stringify(selectedAddress),
      });
      router.push("/interview?welcome=nanny");
      router.refresh();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "We couldn't create your account. Please try again.",
      );
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen px-5 py-6 sm:px-8 sm:py-10">
      <div className="mx-auto max-w-6xl">
        <header className="flex items-center justify-between gap-4">
          <Brand large />
          <Link href={nextPath === "/placements" ? "/login?next=%2Fplacements" : "/login"} className="btn-secondary">
            Sign in
          </Link>
        </header>

        <div className="mt-8 grid items-start gap-8 lg:grid-cols-[.72fr_1.28fr]">
          <aside className="relative overflow-hidden rounded-[32px] bg-[var(--blue-dark)] p-7 text-white lg:sticky lg:top-8 lg:p-9">
            <div className="absolute -right-20 -top-20 h-64 w-64 rounded-full border-[54px] border-white/5" />
            <div className="relative">
              <div className="eyebrow !text-[#bfe5f3]">Join My Nanny</div>
              <h1 className="display mt-4 text-4xl leading-tight sm:text-5xl">
                {role === "nanny"
                  ? "Let families get to know the real you."
                  : isPermanentParent
                    ? "Find the right nanny for the long term."
                    : "Find trusted care for your family."}
              </h1>
              <p className="mt-5 leading-7 text-white/70">
                {role === "nanny"
                  ? accountCreated
                    ? "Your account is secure. Now complete the private information our screening team needs to review your application."
                    : "Create your account first. Your application and screening questions only appear once you are signed in."
                  : isPermanentParent
                    ? "Create your private family account, then choose Self-Match or Concierge and tell us what your family needs."
                    : "Create your private family account to discover video-screened nannies and manage bookings."}
              </p>
              <div className="mt-8 grid gap-4 text-sm font-bold text-white/80">
                {(role === "nanny"
                  ? [
                      "Your details stay private",
                      "Complete screening step by step",
                      "Build trust through your video",
                    ]
                  : [
                      "Only screened nannies are shown",
                      "Contact details remain protected",
                      isPermanentParent
                        ? "Shortlists, interviews and offers stay together"
                        : "Bookings stay in one place",
                    ]
                ).map((item) => (
                  <span key={item} className="flex items-center gap-3">
                    <BadgeCheck size={18} className="text-[#bfe5f3]" />
                    {item}
                  </span>
                ))}
              </div>
            </div>
          </aside>

          <section className="card p-6 sm:p-9">
            <Link
              href="/"
              className="mb-6 inline-flex items-center gap-2 text-sm font-bold text-[var(--muted)]"
            >
              <ArrowLeft size={16} /> Back home
            </Link>
            <div className="eyebrow">
              {accountCreated ? "Private application" : "Create account"}
            </div>
            <h2 className="display mt-2 text-4xl">
              {accountCreated
                ? "Complete your nanny profile."
                : "Tell us who you are."}
            </h2>
            {!accountCreated && (
              <div className="mt-6 grid grid-cols-2 gap-2 rounded-2xl bg-[var(--blue-pale)] p-1.5">
                {(["parent", "nanny"] as Role[]).map((value) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => chooseRole(value)}
                    className={`flex min-h-12 items-center justify-center gap-2 rounded-xl text-sm font-extrabold transition ${role === value ? "bg-white text-[var(--blue-dark)] shadow-sm" : "text-[var(--muted)]"}`}
                  >
                    <UserRound size={17} />
                    {value === "parent" ? "I am a parent" : "I am a nanny"}
                  </button>
                ))}
              </div>
            )}

            <form onSubmit={submit} className="mt-8 grid gap-7">
              {!accountCreated && (
                <fieldset className="grid gap-4 sm:grid-cols-2">
                  <legend className="mb-4 text-lg font-extrabold">
                    Account details
                  </legend>
                  <Field
                    label="Full name"
                    required
                    value={form.name}
                    onChange={(value) => update("name", value)}
                  />
                  <Field
                    label="Mobile number"
                    required
                    type="tel"
                    placeholder="+27"
                    value={form.phone}
                    onChange={(value) => update("phone", value)}
                  />
                  <Field
                    label="Email address"
                    required
                    type="email"
                    value={form.email}
                    onChange={(value) => update("email", value)}
                  />
                  <Field
                    label="Password"
                    required
                    minLength={6}
                    type="password"
                    placeholder="At least 6 characters"
                    value={form.password}
                    onChange={(value) => update("password", value)}
                  />
                </fieldset>
              )}

              {role === "nanny" && accountCreated && (
                <>
                  <fieldset className="grid gap-4 border-t border-[var(--line)] pt-7 sm:grid-cols-2">
                    <legend className="mb-4 text-lg font-extrabold">
                      Identity and eligibility
                    </legend>
                    <Field
                      label="Alternative phone"
                      type="tel"
                      value={form.phoneAlt}
                      onChange={(value) => update("phoneAlt", value)}
                    />
                    <Select
                      label="Nationality"
                      required
                      value={form.nationality}
                      onChange={(value) => update("nationality", value)}
                      options={[
                        ["Angolan", "Angolan"],
                        ["Botswanan", "Botswanan"],
                        ["Comorian", "Comorian"],
                        ["Congolese (DRC)", "Congolese (DRC)"],
                        ["Eswatini", "Eswatini"],
                        ["Lesotho", "Lesotho"],
                        ["Madagascan", "Madagascan"],
                        ["Malawian", "Malawian"],
                        ["Mauritian", "Mauritian"],
                        ["Mozambican", "Mozambican"],
                        ["Namibian", "Namibian"],
                        ["Seychellois", "Seychellois"],
                        ["South African", "South African"],
                        ["Tanzanian", "Tanzanian"],
                        ["Zambian", "Zambian"],
                        ["Zimbabwean", "Zimbabwean"],
                      ]}
                    />
                    <Select
                      label="Gender"
                      required
                      value={form.gender}
                      onChange={(value) => update("gender", value)}
                      options={[
                        ["female", "Female"],
                        ["male", "Male"],
                        ["other", "Other"],
                      ]}
                    />
                    <Select
                      label="Race"
                      required
                      value={form.ethnicity}
                      onChange={(value) => update("ethnicity", value)}
                      options={[
                        ["black", "Black"],
                        ["coloured", "Coloured"],
                        ["indian", "Indian"],
                        ["white", "White"],
                        ["other", "Other"],
                      ]}
                    />
                    {isSouthAfrican ? (
                      <Field
                        label="South African ID number"
                        required
                        inputMode="numeric"
                        maxLength={13}
                        value={form.saIdNumber}
                        onChange={(value) =>
                          update("saIdNumber", value.replace(/\D/g, ""))
                        }
                      />
                    ) : (
                      <>
                        <Field
                          label="Passport number"
                          required
                          value={form.passportNumber}
                          onChange={(value) => update("passportNumber", value)}
                        />
                        <Field
                          label="Passport expiry"
                          required
                          type="date"
                          value={form.passportExpiry}
                          onChange={(value) => update("passportExpiry", value)}
                        />
                        <Select
                          label="Permit status"
                          required
                          value={form.permitStatus}
                          onChange={(value) => update("permitStatus", value)}
                          options={[
                            ["permit", "Valid work permit"],
                            ["waiver", "Waiver"],
                            ["receipt", "Application receipt"],
                          ]}
                        />
                        {form.permitStatus === "permit" && (
                          <Field
                            label="Permit expiry"
                            required
                            type="date"
                            value={form.workPermitExpiry}
                            onChange={(value) =>
                              update("workPermitExpiry", value)
                            }
                          />
                        )}
                      </>
                    )}
                  </fieldset>

                  <fieldset className="grid gap-4 border-t border-[var(--line)] pt-7 sm:grid-cols-2">
                    <legend className="mb-4 text-lg font-extrabold">
                      Work and screening
                    </legend>
                    <Select
                      label="Preferred job type"
                      required
                      value={form.jobType}
                      onChange={(value) => update("jobType", value)}
                      options={[
                        ["stay_in", "Stay in"],
                        ["stay_out", "Stay out"],
                        ["both", "Both"],
                      ]}
                    />
                    <Select
                      label="Police clearance"
                      required
                      value={form.policeClearanceStatus}
                      onChange={(value) =>
                        update("policeClearanceStatus", value)
                      }
                      options={[
                        ["yes", "Yes"],
                        ["not_yet", "Not yet"],
                      ]}
                    />
                    <Select
                      label="Do you have your own car?"
                      required
                      value={form.hasOwnCar}
                      onChange={(value) => update("hasOwnCar", value)}
                      options={[
                        ["yes", "Yes"],
                        ["no", "No"],
                      ]}
                    />
                    <Select
                      label="Do you have a driver’s license?"
                      required={form.hasOwnCar === "yes"}
                      value={form.hasDriversLicense}
                      onChange={(value) => update("hasDriversLicense", value)}
                      options={[
                        ["yes", "Yes"],
                        ["no", "No"],
                      ]}
                    />
                    <Select
                      label="Do you have children?"
                      required
                      value={form.hasOwnKids}
                      onChange={(value) => update("hasOwnKids", value)}
                      options={[
                        ["yes", "Yes"],
                        ["no", "No"],
                      ]}
                    />
                    <Select
                      label="My Nanny training completed?"
                      required
                      value={form.trainingStatus}
                      onChange={(value) => update("trainingStatus", value)}
                      options={[
                        ["yes", "Yes"],
                        ["not_yet", "Not yet"],
                      ]}
                    />
                    {form.hasOwnKids === "yes" && (
                      <label className="sm:col-span-2">
                        <span className="mb-2 block text-sm font-bold">
                          Children’s ages and where they stay
                        </span>
                        <textarea
                          required
                          className="field min-h-24 resize-y"
                          value={form.ownKidsDetails}
                          onChange={(event) =>
                            update("ownKidsDetails", event.target.value)
                          }
                        />
                      </label>
                    )}
                    <label className="sm:col-span-2">
                      <span className="mb-2 block text-sm font-bold">
                        Medical conditions or chronic medication
                      </span>
                      <textarea
                        className="field min-h-24 resize-y"
                        placeholder="Write None if not applicable"
                        value={form.medicalConditions}
                        onChange={(event) =>
                          update("medicalConditions", event.target.value)
                        }
                      />
                    </label>
                  </fieldset>

                  <div className="grid gap-4 rounded-2xl border border-[var(--line)] bg-[var(--blue-pale)] p-5">
                    <div className="flex gap-4">
                      <MapPin
                        className="mt-0.5 shrink-0 text-[var(--blue)]"
                        size={24}
                      />
                      <div>
                        <div className="font-extrabold">
                          Home location required
                        </div>
                        <p className="mt-1 text-sm leading-6 text-[var(--muted)]">
                          We will use GPS first, show you the matching address,
                          and ask you to confirm that you live there. If it is
                          incorrect, you can enter your address manually.
                        </p>
                      </div>
                    </div>
                    <NannyLocationConfirmation
                      onConfirm={(address) => setSelectedAddress(address)}
                      onReset={() => setSelectedAddress(null)}
                    />
                  </div>
                </>
              )}

              {error && (
                <div
                  role="alert"
                  className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700"
                >
                  {error}
                </div>
              )}
              <div>
                <button
                  disabled={loading}
                  className="btn-primary w-full sm:w-auto"
                >
                  {loading
                    ? "Creating your account..."
                    : accountCreated
                      ? "Save location and continue"
                      : role === "nanny"
                        ? "Create my nanny account"
                        : "Create my account"}
                  <ArrowRight size={18} />
                </button>
                <p className="mt-4 text-xs leading-5 text-[var(--muted)]">
                  By continuing, you confirm that the information supplied is
                  accurate and may be used for account verification.
                </p>
              </div>
            </form>
          </section>
        </div>
        <footer className="mt-10 flex justify-center border-t border-[var(--line)] pt-8 sm:justify-end">
          <PoweredByTiqet />
        </footer>
      </div>
    </main>
  );
}

function Field({
  label,
  onChange,
  ...props
}: Omit<React.InputHTMLAttributes<HTMLInputElement>, "onChange"> & {
  label: string;
  onChange: (value: string) => void;
}) {
  return (
    <label>
      <span className="mb-2 block text-sm font-bold">{label}</span>
      <input
        {...props}
        className="field"
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function Select({
  label,
  options,
  onChange,
  ...props
}: Omit<React.SelectHTMLAttributes<HTMLSelectElement>, "onChange"> & {
  label: string;
  options: [string, string][];
  onChange: (value: string) => void;
}) {
  return (
    <label>
      <span className="mb-2 block text-sm font-bold">{label}</span>
      <select
        {...props}
        className="field"
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">Select</option>
        {options.map(([value, text]) => (
          <option key={value} value={value}>
            {text}
          </option>
        ))}
      </select>
    </label>
  );
}

export default function SignupPage() {
  return (
    <Suspense fallback={<main className="min-h-screen" />}>
      <SignupForm />
    </Suspense>
  );
}
