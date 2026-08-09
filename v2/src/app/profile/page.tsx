"use client";
/* eslint-disable @typescript-eslint/no-explicit-any */

import { AuthenticatedPage } from "@/components/authenticated-page";
import { apiFetch, apiJson } from "@/lib/api";
import { Camera, Check, CreditCard, FileUp, KeyRound, LoaderCircle, MapPin, Save, Settings2, ShieldCheck, Wallet } from "lucide-react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

type Data = Record<string, any>;
type NamedOption = { id: number; name: string };
type ParentLocation = {
  id: number;
  label?: string | null;
  formatted_address?: string | null;
  suburb?: string | null;
  city?: string | null;
  lat: number;
  lng: number;
  is_default: boolean;
};
type PaymentMethod = {
  has_card: boolean;
  card_brand?: string | null;
  card_last4?: string | null;
};
const nationalities = [
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
];

function southAfricanPhoneInput(value: string) {
  const digits = value.replace(/\D/g, "");
  const national = digits.startsWith("27")
    ? digits.slice(2)
    : digits.startsWith("0")
      ? digits.slice(1)
      : digits;
  return `+27${national.slice(0, 9)}`;
}

export default function ProfilePage() {
  return (
    <AuthenticatedPage>
      {(role) =>
        role === "parent" ? (
          <ParentProfile />
        ) : role === "nanny" ? (
          <NannyProfile />
        ) : (
          <AdminSettings />
        )
      }
    </AuthenticatedPage>
  );
}

function ParentProfile() {
  const router = useRouter();
  const [data, setData] = useState<Data>({
    kids_count: 0,
    kids_ages: [],
    access_flags: [],
  });
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState("");
  const [careNeeds, setCareNeeds] = useState<NamedOption[]>([]);
  const [languages, setLanguages] = useState<NamedOption[]>([]);
  const [locations, setLocations] = useState<ParentLocation[]>([]);
  const [locating, setLocating] = useState(false);
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod | null>(null);
  const [paymentBusy, setPaymentBusy] = useState(false);
  useEffect(() => {
    Promise.all([
      apiJson<Data>("/parents/me/profile"),
      apiJson<NamedOption[]>("/nanny-tags"),
      apiJson<NamedOption[]>("/languages"),
      apiJson<ParentLocation[]>("/parents/me/locations"),
      apiJson<PaymentMethod>("/parent/payment-method"),
    ])
      .then(([value, tags, languageOptions, savedLocations, payment]) => {
        setData((current) => ({
          ...current,
          ...value,
          phone: southAfricanPhoneInput(value.phone || ""),
        }));
        setCareNeeds(tags);
        setLanguages(languageOptions);
        setLocations(savedLocations);
        setPaymentMethod(payment);
      })
      .catch((e) => setStatus(e.message))
      .finally(() => setLoading(false));
    const params = new URLSearchParams(window.location.search);
    const reference = params.get("reference") || params.get("trxref");
    if (params.get("payment_method") === "verify" && reference) {
      apiJson<PaymentMethod>("/parent/payment-method/verify", {
        method: "POST",
        body: JSON.stringify({ reference }),
      }).then((payment) => {
        setPaymentMethod(payment);
        setStatus("Paystack authorisation completed. You can now request bookings.");
        params.delete("payment_method");
        params.delete("reference");
        params.delete("trxref");
        window.history.replaceState({}, "", `${window.location.pathname}${params.toString() ? `?${params}` : ""}`);
      }).catch((error) => setStatus(error instanceof Error ? error.message : "Unable to verify Paystack authorisation."));
    }
  }, []);
  function set(key: string, value: any) {
    setData((current) => ({ ...current, [key]: value }));
  }
  function setKids(count: number) {
    set("kids_count", count);
    set(
      "kids_ages",
      Array.from(
        { length: count },
        (_, i) => data.kids_ages?.[i] || { years: null, months: null },
      ),
    );
  }
  async function save() {
    setStatus("Saving...");
    try {
      await apiJson("/parents/me/profile", {
        method: "PATCH",
        body: JSON.stringify(data),
      });
      setStatus("Profile saved.");
      window.sessionStorage.setItem("parent-profile-saved", "true");
      window.setTimeout(() => router.push("/dashboard"), 2000);
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "Unable to save.");
    }
  }
  async function captureCurrentLocation() {
    if (!navigator.geolocation) {
      setStatus("Location services are not available in this browser.");
      return;
    }
    setLocating(true);
    setStatus("Finding your location...");
    navigator.geolocation.getCurrentPosition(
      async ({ coords }) => {
        try {
          const location = await apiJson<ParentLocation>("/parents/me/locations", {
            method: "POST",
            body: JSON.stringify({
              label: "Home",
              lat: coords.latitude,
              lng: coords.longitude,
              is_default: locations.length === 0,
            }),
          });
          setLocations((current) => {
            const withoutDuplicate = current.filter((item) => item.id !== location.id);
            return [location, ...withoutDuplicate];
          });
          setStatus("Home location saved.");
        } catch (error) {
          setStatus(error instanceof Error ? error.message : "Unable to save location.");
        } finally {
          setLocating(false);
        }
      },
      () => {
        setLocating(false);
        setStatus("Allow location access in your browser, then try again.");
      },
      { enableHighAccuracy: true, timeout: 15000 },
    );
  }
  async function makeDefaultLocation(locationId: number) {
    try {
      await apiJson(`/parents/me/locations/${locationId}/default`, {
        method: "PATCH",
        body: JSON.stringify({ make_default: true }),
      });
      setLocations((current) =>
        current.map((location) => ({
          ...location,
          is_default: location.id === locationId,
        })),
      );
      setStatus("Default booking location updated.");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Unable to update location.");
    }
  }
  async function authorisePaystack() {
    setPaymentBusy(true);
    setStatus("");
    try {
      const callback = new URL(window.location.href);
      callback.searchParams.set("payment_method", "verify");
      const result = await apiJson<{ authorization_url?: string }>("/parent/payment-method/initialize", {
        method: "POST",
        body: JSON.stringify({ callback_url: callback.toString() }),
      });
      if (!result.authorization_url) throw new Error("Paystack authorisation could not be started.");
      window.location.href = result.authorization_url;
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Unable to open Paystack.");
      setPaymentBusy(false);
    }
  }
  if (loading) return <Loading />;
  return (
    <ProfileLayout
      title="Your family profile"
      intro="Keep these details current so bookings are faster and nannies receive the right information."
    >
      <section className={`mb-6 rounded-3xl border p-6 ${paymentMethod?.has_card ? "border-emerald-200 bg-emerald-50" : "border-amber-200 bg-amber-50"}`}>
        <div className="flex flex-wrap items-center justify-between gap-5">
          <div className="flex items-start gap-4">
            <span className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-white ${paymentMethod?.has_card ? "text-[var(--green)]" : "text-amber-700"}`}>
              {paymentMethod?.has_card ? <ShieldCheck /> : <CreditCard />}
            </span>
            <div>
              <h2 className="text-xl font-bold">Booking payment authorisation</h2>
              <p className="mt-1 max-w-2xl text-sm leading-6 text-[var(--muted)]">
                {paymentMethod?.has_card
                  ? `Completed securely through Paystack${paymentMethod.card_brand && paymentMethod.card_last4 ? ` · ${paymentMethod.card_brand} ending ${paymentMethod.card_last4}` : ""}. My Nanny does not store your card details.`
                  : "You will not be able to request a booking until Paystack authorisation has been completed. Paystack securely handles your card details; My Nanny does not store them."}
              </p>
            </div>
          </div>
          {paymentMethod?.has_card ? (
            <span className="pill !border-emerald-200 !bg-white text-emerald-800"><Check size={15} />Complete</span>
          ) : (
            <button className="btn-primary shrink-0" disabled={paymentBusy} onClick={() => void authorisePaystack()}>{paymentBusy ? <LoaderCircle className="animate-spin" size={17} /> : <ShieldCheck size={17} />}{paymentBusy ? "Opening Paystack..." : "Complete with Paystack"}</button>
          )}
        </div>
      </section>
      <Section title="Family details">
        <Grid>
          <Input
            label="Phone number"
            type="tel"
            inputMode="tel"
            autoComplete="tel"
            placeholder="+27821234567"
            maxLength={12}
            value={data.phone}
            onChange={(v) => set("phone", southAfricanPhoneInput(v))}
          />
          <Input
            label="Number of children"
            type="number"
            min={0}
            max={10}
            value={data.kids_count}
            onChange={(v) => setKids(Number(v))}
          />
          {(data.kids_ages || []).map((age: Data, i: number) => (
            <div key={i} className="grid grid-cols-2 gap-3">
              <Input
                label={`Child ${i + 1}: years`}
                type="number"
                min={0}
                value={age.years ?? ""}
                onChange={(v) => {
                  const ages = [...data.kids_ages];
                  ages[i] = { ...ages[i], years: v === "" ? null : Number(v) };
                  set("kids_ages", ages);
                }}
              />
              <Input
                label="Months"
                type="number"
                min={0}
                max={11}
                value={age.months ?? ""}
                onChange={(v) => {
                  const ages = [...data.kids_ages];
                  ages[i] = { ...ages[i], months: v === "" ? null : Number(v) };
                  set("kids_ages", ages);
                }}
              />
            </div>
          ))}
          <Select
            label="Type of residence"
            value={data.residence_type}
            onChange={(v) => set("residence_type", v)}
            options={[
              ["open_street", "Open residential street"],
              ["gated", "Gated community"],
              ["access_required", "Access required"],
            ]}
          />
          <Input
            label="Access instructions"
            placeholder="Example: Call on arrival for a gate code"
            hint="Explain whether the nanny must arrange access in advance, needs a gate or access code, must sign in with security, or should call someone on arrival."
            value={(data.access_flags || []).join(", ")}
            onChange={(v) => set("access_flags", v ? [v] : [])}
          />
          <Textarea
            label="Family notes"
            value={data.special_notes}
            onChange={(v) => set("special_notes", v)}
          />
          <Select
            label="Home language"
            value={data.home_language_id ? String(data.home_language_id) : ""}
            onChange={(v) => set("home_language_id", v ? Number(v) : null)}
            options={languages.map((language) => [String(language.id), language.name])}
          />
          <MultiSelect
            label="Care needs"
            hint="Choose the childcare experience that would be most helpful for your family."
            options={careNeeds}
            value={data.desired_tag_ids || []}
            onChange={(value) => set("desired_tag_ids", value)}
          />
        </Grid>
      </Section>
      <Section title="Booking locations">
        <p className="mb-5 text-sm text-[var(--muted)]">
          Your location is used for distance-based nanny matching. Exact details are only shared when needed for a booking.
        </p>
        <div className="grid gap-3">
          {locations.map((location) => (
            <div key={location.id} className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[var(--line)] p-4">
              <div>
                <div className="font-bold">{location.label || "Saved location"}</div>
                <div className="text-sm text-[var(--muted)]">
                  {location.formatted_address || [location.suburb, location.city].filter(Boolean).join(", ") || `${location.lat.toFixed(5)}, ${location.lng.toFixed(5)}`}
                </div>
              </div>
              {location.is_default ? (
                <span className="pill text-emerald-700">Default</span>
              ) : (
                <button className="btn-secondary !min-h-10" onClick={() => void makeDefaultLocation(location.id)}>
                  Make default
                </button>
              )}
            </div>
          ))}
          {!locations.length && (
            <div className="rounded-2xl bg-slate-50 p-5 text-sm text-[var(--muted)]">No booking location saved yet.</div>
          )}
        </div>
        <button className="btn-secondary mt-4" disabled={locating} onClick={() => void captureCurrentLocation()}>
          <MapPin size={18} /> {locating ? "Finding location..." : "Use my current location"}
        </button>
      </Section>
      <Section title="Booking defaults">
        <Grid>
          <Textarea
            label="Typical nanny responsibilities"
            value={data.booking_responsibilities}
            onChange={(v) => set("booking_responsibilities", v)}
          />
          <Select
            label="Adult usually present"
            value={data.booking_adult_present}
            onChange={(v) => set("booking_adult_present", v)}
            options={[
              ["parent", "I will be present"],
              ["other_adult", "Another adult"],
              ["none", "No adult"],
            ]}
          />
          <Select
            label="Meal arrangement"
            value={data.booking_meal_option}
            onChange={(v) => set("booking_meal_option", v)}
            options={[
              ["meal_provided", "We provide a meal"],
              ["basics_provided", "We provide basics"],
              ["own_meal", "Nanny brings a meal"],
            ]}
          />
          <Input
            label="Food restrictions"
            placeholder="Example: No nuts or pork in the house"
            hint="List any allergies, dietary, religious or cultural restrictions, including foods the nanny must not bring into or prepare in your home. Enter “None” if there are no restrictions."
            value={data.booking_food_restrictions}
            onChange={(v) => set("booking_food_restrictions", v)}
          />
          <Input
            label="Dogs at home"
            value={data.booking_dogs}
            onChange={(v) => set("booking_dogs", v)}
          />
        </Grid>
      </Section>
      <SaveBar status={status} onSave={save} />
    </ProfileLayout>
  );
}

function NannyProfile() {
  const [data, setData] = useState<Data>({});
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState("");
  useEffect(() => {
    apiJson<Data>("/nannies/me/profile")
      .then(setData)
      .catch((e) => setStatus(e.message))
      .finally(() => setLoading(false));
  }, []);
  function set(key: string, value: any) {
    setData((current) => ({ ...current, [key]: value }));
  }
  async function save() {
    setStatus("Saving...");
    try {
      await apiJson("/nannies/me/profile", {
        method: "PATCH",
        body: JSON.stringify(data),
      });
      setStatus("Application saved.");
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "Unable to save.");
    }
  }
  async function captureLocation() {
    setStatus("Requesting your location...");
    try {
      const position = await new Promise<GeolocationPosition>(
        (resolve, reject) => {
          if (!navigator.geolocation) {
            reject(
              new Error("Location services are not available on this device."),
            );
            return;
          }
          navigator.geolocation.getCurrentPosition(resolve, reject, {
            enableHighAccuracy: true,
            timeout: 20_000,
            maximumAge: 0,
          });
        },
      );
      await apiJson("/nannies/me/location", {
        method: "PATCH",
        body: JSON.stringify({
          lat: position.coords.latitude,
          lng: position.coords.longitude,
        }),
      });
      const refreshed = await apiJson<Data>("/nannies/me/profile");
      setData(refreshed);
      setStatus("Home location saved.");
    } catch (e) {
      setStatus(
        e instanceof Error
          ? e.message
          : "Allow location access to save your home location.",
      );
    }
  }
  async function upload(path: string, file: File, key: string, append = false) {
    setStatus("Uploading...");
    const body = new FormData();
    body.append("file", file);
    if (path === "/nannies/me/passport-document") {
      if (!data.passport_expiry) {
        setStatus("Enter the new passport expiry date before uploading.");
        return;
      }
      body.append("expiry_date", data.passport_expiry);
    }
    const res = await apiFetch(path, { method: "POST", body });
    if (!res.ok) {
      setStatus(await res.text());
      return;
    }
    const result = await res.json();
    setData((current) => ({
      ...current,
      [key]: append
        ? [...(Array.isArray(current[key]) ? current[key] : []), result.url]
        : result.url,
    }));
    setStatus("Document uploaded.");
  }
  async function uploadPhoto(file?: File) {
    if (!file) return;
    setStatus("Uploading profile photo...");
    const body = new FormData();
    body.append("file", file);
    const res = await apiFetch("/nannies/me/photo", { method: "POST", body });
    if (!res.ok) {
      setStatus(await res.text());
      return;
    }
    const result = await res.json();
    setData((current) => ({ ...current, profile_photo_url: result.url }));
    setStatus("Profile photo updated.");
  }
  if (loading) return <Loading />;
  const sa = (data.nationality || "").toLowerCase() === "south african";
  return (
    <ProfileLayout
      title="Your nanny profile"
      intro="Your application is private until screening and approval. You can save and return at any time."
    >
      <Section title="Profile photo">
        <div className="flex flex-wrap items-center gap-5">
          {data.profile_photo_url ? (
            <Image
              src={data.profile_photo_url}
              alt="Your profile"
              width={112}
              height={112}
              className="h-28 w-28 rounded-3xl object-cover"
              unoptimized
            />
          ) : (
            <div className="flex h-28 w-28 items-center justify-center rounded-3xl bg-[var(--blue-pale)] text-[var(--blue)]">
              <Camera size={34} />
            </div>
          )}
          <div>
            <label className="btn-secondary cursor-pointer">
              <Camera size={17} />
              {data.profile_photo_url ? "Replace photo" : "Upload photo"}
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp"
                className="sr-only"
                onChange={(event) => void uploadPhoto(event.target.files?.[0])}
              />
            </label>
            <p className="mt-2 text-sm text-[var(--muted)]">
              Use a clear, recent head-and-shoulders photo. JPG, PNG or WebP.
            </p>
          </div>
        </div>
      </Section>
      <Section title="Personal details">
        <Grid>
          <Input
            label="Full name"
            value={data.full_name}
            onChange={(v) => set("full_name", v)}
          />
          <Input
            label="Phone"
            value={data.phone}
            onChange={(v) => set("phone", v)}
          />
          <Input
            label="Alternative phone"
            value={data.phone_alt}
            onChange={(v) => set("phone_alt", v)}
          />
          <Input
            label="Date of birth"
            type="date"
            value={data.dob}
            onChange={(v) => set("dob", v)}
          />
          <Select
            label="Gender"
            value={data.gender}
            onChange={(v) => set("gender", v)}
            options={[
              ["Female", "Female"],
              ["Male", "Male"],
              ["Other", "Other"],
            ]}
          />
          <Select
            label="Race"
            value={data.ethnicity}
            onChange={(v) => set("ethnicity", v)}
            options={[
              ["Black", "Black"],
              ["Coloured", "Coloured"],
              ["Indian/Asian", "Indian/Asian"],
              ["White", "White"],
              ["Other", "Other"],
            ]}
          />
          <Select
            label="Nationality"
            value={data.nationality}
            onChange={(v) => set("nationality", v)}
            options={nationalities.map((v) => [v, v])}
          />
          <Textarea
            label="Profile introduction"
            value={data.bio}
            onChange={(v) => set("bio", v)}
          />
        </Grid>
      </Section>
      <Section title="Home location">
        <div className="flex flex-col gap-5 rounded-2xl bg-[var(--blue-pale)] p-5 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-white text-[var(--blue)] shadow-sm">
              {data.lat != null && data.lng != null ? (
                <Check size={22} />
              ) : (
                <MapPin size={22} />
              )}
            </div>
            <div>
              <div className="font-extrabold">
                {data.lat != null && data.lng != null
                  ? "Location on file"
                  : "Location required"}
              </div>
              <p className="mt-1 text-sm leading-6 text-[var(--muted)]">
                {data.formatted_address ||
                  [data.suburb, data.city].filter(Boolean).join(", ") ||
                  "Add your location before submitting your video interview."}{" "}
                Your exact address is not shown to parents.
              </p>
            </div>
          </div>
          <button className="btn-secondary shrink-0" onClick={captureLocation}>
            <MapPin size={17} />
            {data.lat != null && data.lng != null
              ? "Update location"
              : "Add my location"}
          </button>
        </div>
      </Section>
      <Section title="Identity and eligibility">
        <Grid>
          {sa ? (
            <Input
              label="South African ID number"
              value={data.sa_id_number}
              onChange={(v) => set("sa_id_number", v)}
            />
          ) : (
            <>
              <Input
                label="Passport number"
                value={data.passport_number}
                onChange={(v) => set("passport_number", v)}
              />
              <Input
                label="Passport expiry"
                type="date"
                value={data.passport_expiry}
                onChange={(v) => set("passport_expiry", v)}
              />
              <Select
                label="Permit status"
                value={data.permit_status}
                onChange={(v) => set("permit_status", v)}
                options={[
                  ["permit", "Valid permit"],
                  ["waiver", "Waiver"],
                  ["receipt", "Application receipt"],
                ]}
              />
            </>
          )}
          <Select
            label="Job type"
            value={data.job_type}
            onChange={(v) => set("job_type", v)}
            options={[
              ["stay_in", "Stay in"],
              ["stay_out", "Stay out"],
              ["both", "Both"],
            ]}
          />
          <YesNo
            label="Own car"
            value={data.has_own_car}
            onChange={(v) => set("has_own_car", v)}
          />
          <YesNo
            label="Driver’s license"
            value={data.has_drivers_license}
            onChange={(v) => set("has_drivers_license", v)}
          />
          <Select
            label="Police clearance"
            value={data.police_clearance_status}
            onChange={(v) => set("police_clearance_status", v)}
            options={[
              ["yes", "Yes"],
              ["not_yet", "Not yet"],
            ]}
          />
          <Select
            label="My Nanny training"
            value={data.my_nanny_training_status}
            onChange={(v) => set("my_nanny_training_status", v)}
            options={[
              ["yes", "Completed"],
              ["not_yet", "Not yet"],
            ]}
          />
        </Grid>
      </Section>
      <Section title="Documents">
        <div className="grid gap-3 sm:grid-cols-2">
          {[
            [
              sa ? "Identity document" : "Passport",
              sa ? "/nannies/me/id-document" : "/nannies/me/passport-document",
              sa ? data.sa_id_document_url : data.passport_document_url,
              sa ? "sa_id_document_url" : "passport_document_url",
            ],
            ...(!sa
              ? [
                  [
                    "Permit / waiver",
                    "/nannies/me/work-permit-document",
                    data.work_permit_document_url,
                    "work_permit_document_url",
                  ],
                ]
              : []),
            [
              "Police clearance",
              "/nannies/me/police-clearance-document",
              data.police_clearance_document_url,
              "police_clearance_document_url",
            ],
            [
              "Driver’s license",
              "/nannies/me/drivers-license-document",
              data.drivers_license_document_url,
              "drivers_license_document_url",
            ],
            [
              "Training certificates (optional)",
              "/nannies/me/certificates",
              data.certificate_urls?.length ? "uploaded" : null,
              "certificate_urls",
            ],
          ].map(([label, path, current, key]) => (
            <Upload
              key={label}
              label={label}
              current={current}
              approved={Boolean(data.is_approved && current)}
              onFile={(file) =>
                upload(path, file, key, key === "certificate_urls")
              }
            />
          ))}
        </div>
      </Section>
      <Section title="Family and health">
        <Grid>
          <YesNo
            label="Do you have children?"
            value={data.has_own_kids}
            onChange={(v) => set("has_own_kids", v)}
          />
          {data.has_own_kids && (
            <Textarea
              label="Their ages and where they stay"
              value={data.own_kids_details}
              onChange={(v) => set("own_kids_details", v)}
            />
          )}
          <Textarea
            label="Medical conditions or chronic medication"
            value={data.medical_conditions}
            onChange={(v) => set("medical_conditions", v)}
          />
        </Grid>
      </Section>
      <SaveBar status={status} onSave={save} />
    </ProfileLayout>
  );
}

function AdminSettings() {
  const [pricing, setPricing] = useState<Data | null>(null);
  const [integration, setIntegration] = useState<Data | null>(null);
  const [mapsKey, setMapsKey] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    Promise.all([
      apiJson<Data>("/admin/pricing"),
      apiJson<Data>("/admin/integrations/google-maps"),
    ]).then(([priceSettings, integrationSettings]) => {
      setPricing({
        ...priceSettings,
        booking_fee_pct_1_5: Number(priceSettings.booking_fee_pct_1_5 || 0) * 100,
        booking_fee_pct_6_10: Number(priceSettings.booking_fee_pct_6_10 || 0) * 100,
        booking_fee_pct_10_plus: Number(priceSettings.booking_fee_pct_10_plus || 0) * 100,
        overrun_hourly_weekday: Number(priceSettings.overrun_hourly_weekday || 0) / 100,
        overrun_hourly_weekend: Number(priceSettings.overrun_hourly_weekend || 0) / 100,
        transport_fee_17_20: Number(priceSettings.transport_fee_17_20 || 0) / 100,
        transport_fee_after_20: Number(priceSettings.transport_fee_after_20 || 0) / 100,
      });
      setIntegration(integrationSettings);
    }).catch((error) => setMessage(error instanceof Error ? error.message : "Unable to load platform settings."))
      .finally(() => setLoading(false));
  }, []);

  function price(key: string, value: string) {
    setPricing((current) => current ? { ...current, [key]: value === "" ? "" : Number(value) } : current);
  }

  async function savePricing() {
    if (!pricing) return;
    const feeKeys = ["booking_fee_pct_1_5", "booking_fee_pct_6_10", "booking_fee_pct_10_plus"];
    if (feeKeys.some((key) => Number(pricing[key]) < 0 || Number(pricing[key]) > 100)) {
      setMessage("Booking fee percentages must be between 0% and 100%.");
      return;
    }
    setSaving("pricing");
    setMessage("");
    try {
      await apiJson("/admin/pricing", {
        method: "PUT",
        body: JSON.stringify({
          ...pricing,
          booking_fee_pct_1_5: Number(pricing.booking_fee_pct_1_5) / 100,
          booking_fee_pct_6_10: Number(pricing.booking_fee_pct_6_10) / 100,
          booking_fee_pct_10_plus: Number(pricing.booking_fee_pct_10_plus) / 100,
          overrun_hourly_weekday: Math.round(Number(pricing.overrun_hourly_weekday) * 100),
          overrun_hourly_weekend: Math.round(Number(pricing.overrun_hourly_weekend) * 100),
          transport_fee_17_20: Math.round(Number(pricing.transport_fee_17_20) * 100),
          transport_fee_after_20: Math.round(Number(pricing.transport_fee_after_20) * 100),
        }),
      });
      setMessage("Pricing and operational rules saved.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to save pricing settings.");
    } finally {
      setSaving("");
    }
  }

  async function saveIntegrations() {
    if (!integration) return;
    setSaving("integrations");
    setMessage("");
    try {
      const payload: Data = { google_calendar_id: integration.google_calendar_id || "" };
      if (mapsKey.trim()) payload.google_maps_api_key = mapsKey.trim();
      const result = await apiJson<Data>("/admin/integrations/google-maps", {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      setIntegration((current) => ({ ...current, ...result, configured: result.configured ?? current?.configured }));
      setMapsKey("");
      setMessage("Integration settings saved.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to save integration settings.");
    } finally {
      setSaving("");
    }
  }

  if (loading) return <Loading />;
  return (
    <ProfileLayout
      title="Platform settings"
      intro="Control booking rates, platform fees, payout timing and location integrations used throughout My Nanny."
    >
      {message && <div className="rounded-2xl bg-[var(--blue-pale)] p-4 text-sm font-semibold">{message}</div>}
      {pricing && (
        <>
          <SettingsPanel icon={<Wallet />} title="Standard booking rates" intro="Customer-facing base rates in South African rand.">
            <SettingsGrid>
              <SettingNumber label="Weekday half day" prefix="R" value={pricing.weekday_half_day} onChange={(value) => price("weekday_half_day", value)} />
              <SettingNumber label="Weekday full day" prefix="R" value={pricing.weekday_full_day} onChange={(value) => price("weekday_full_day", value)} />
              <SettingNumber label="Weekend half day" prefix="R" value={pricing.weekend_half_day} onChange={(value) => price("weekend_half_day", value)} />
              <SettingNumber label="Weekend full day" prefix="R" value={pricing.weekend_full_day} onChange={(value) => price("weekend_full_day", value)} />
              <SettingNumber label="After 17:00 weekday" prefix="R" value={pricing.after17_weekday} onChange={(value) => price("after17_weekday", value)} />
              <SettingNumber label="After 17:00 weekend" prefix="R" value={pricing.after17_weekend} onChange={(value) => price("after17_weekend", value)} />
              <SettingNumber label="Over 9 hours weekday" prefix="R" value={pricing.over9_weekday} onChange={(value) => price("over9_weekday", value)} />
              <SettingNumber label="Over 9 hours weekend" prefix="R" value={pricing.over9_weekend} onChange={(value) => price("over9_weekend", value)} />
            </SettingsGrid>
          </SettingsPanel>

          <SettingsPanel icon={<Settings2 />} title="Sleepover rates" intro="Rates and time boundaries applied to overnight care.">
            <SettingsGrid>
              <SettingNumber label="Sleepover add-on" prefix="R" value={pricing.sleepover_add} onChange={(value) => price("sleepover_add", value)} />
              <SettingNumber label="Sleepover only · weekday" prefix="R" value={pricing.sleepover_only_weekday} onChange={(value) => price("sleepover_only_weekday", value)} />
              <SettingNumber label="Sleepover only · weekend" prefix="R" value={pricing.sleepover_only_weekend} onChange={(value) => price("sleepover_only_weekend", value)} />
              <SettingNumber label="Extra hour over 14 hours" prefix="R" value={pricing.sleepover_extra_hour_over14} onChange={(value) => price("sleepover_extra_hour_over14", value)} />
              <SettingNumber label="Sleepover starts" suffix=":00" min={0} max={23} value={pricing.sleepover_start_hour} onChange={(value) => price("sleepover_start_hour", value)} />
              <SettingNumber label="Sleepover ends" suffix=":00" min={0} max={23} value={pricing.sleepover_end_hour} onChange={(value) => price("sleepover_end_hour", value)} />
              <SettingNumber label="Hourly rate after end" prefix="R" value={pricing.sleepover_after7_hourly} onChange={(value) => price("sleepover_after7_hourly", value)} />
            </SettingsGrid>
          </SettingsPanel>

          <SettingsPanel icon={<CreditCard />} title="Platform fees" intro="Percentage charged according to the number of nannies requested.">
            <SettingsGrid>
              <SettingNumber label="1-5 nannies" suffix="%" step="0.1" value={pricing.booking_fee_pct_1_5} onChange={(value) => price("booking_fee_pct_1_5", value)} />
              <SettingNumber label="6-10 nannies" suffix="%" step="0.1" value={pricing.booking_fee_pct_6_10} onChange={(value) => price("booking_fee_pct_6_10", value)} />
              <SettingNumber label="More than 10 nannies" suffix="%" step="0.1" value={pricing.booking_fee_pct_10_plus} onChange={(value) => price("booking_fee_pct_10_plus", value)} />
            </SettingsGrid>
          </SettingsPanel>

          <SettingsPanel icon={<ShieldCheck />} title="Overtime, cancellation and payout" intro="Operational timing and additional charges used by the live booking engine.">
            <SettingsGrid>
              <SettingNumber label="Weekday overtime rate" prefix="R" suffix="/hour" step="0.01" value={pricing.overrun_hourly_weekday} onChange={(value) => price("overrun_hourly_weekday", value)} />
              <SettingNumber label="Weekend overtime rate" prefix="R" suffix="/hour" step="0.01" value={pricing.overrun_hourly_weekend} onChange={(value) => price("overrun_hourly_weekend", value)} />
              <SettingNumber label="Cancellation window" suffix="hours" value={pricing.cancellation_fee_window_hours} onChange={(value) => price("cancellation_fee_window_hours", value)} />
              <SettingNumber label="Overtime query hold" suffix="hours" value={pricing.overrun_hold_hours} onChange={(value) => price("overrun_hold_hours", value)} />
              <SettingNumber label="Payout hold" suffix="hours" value={pricing.payout_hold_hours} onChange={(value) => price("payout_hold_hours", value)} />
            </SettingsGrid>
          </SettingsPanel>

          <SettingsPanel icon={<MapPin />} title="Safe transport" intro="Transport charges and the evening thresholds at which they apply.">
            <SettingsGrid>
              <SettingNumber label="First evening threshold" suffix=":00" min={0} max={23} value={pricing.transport_threshold_1} onChange={(value) => price("transport_threshold_1", value)} />
              <SettingNumber label="Transport fee after first threshold" prefix="R" step="0.01" value={pricing.transport_fee_17_20} onChange={(value) => price("transport_fee_17_20", value)} />
              <SettingNumber label="Second evening threshold" suffix=":00" min={0} max={23} value={pricing.transport_threshold_2} onChange={(value) => price("transport_threshold_2", value)} />
              <SettingNumber label="Transport fee after second threshold" prefix="R" step="0.01" value={pricing.transport_fee_after_20} onChange={(value) => price("transport_fee_after_20", value)} />
            </SettingsGrid>
          </SettingsPanel>

          <div className="sticky bottom-4 z-10 flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-[var(--line)] bg-white/95 p-4 shadow-xl backdrop-blur">
            <p className="text-sm text-[var(--muted)]">Changes affect new estimates and bookings. Existing quoted bookings retain their recorded amounts.</p>
            <button className="btn-primary" disabled={saving === "pricing"} onClick={() => void savePricing()}>{saving === "pricing" ? <LoaderCircle className="animate-spin" size={17} /> : <Save size={17} />}{saving === "pricing" ? "Saving..." : "Save booking settings"}</button>
          </div>
        </>
      )}

      {integration && (
        <SettingsPanel icon={<KeyRound />} title="Google integrations" intro="Used for address search, maps, distance matching and operational calendar synchronisation.">
          <div className="grid gap-5">
            <label><span className="mb-2 block text-sm font-bold">Google Maps API key</span><input type="password" className="field" value={mapsKey} onChange={(event) => setMapsKey(event.target.value)} placeholder={integration.configured || integration.server_env_configured ? "Configured · enter a new key to replace it" : "Enter Google Maps API key"} /><small className="mt-2 block text-[var(--muted)]">{integration.configured ? "Database key configured" : integration.server_env_configured ? "Server environment key configured" : "Not configured"}</small></label>
            <label><span className="mb-2 block text-sm font-bold">Google Calendar ID</span><input className="field" value={integration.google_calendar_id || ""} onChange={(event) => setIntegration((current) => ({ ...current, google_calendar_id: event.target.value }))} /><small className="mt-2 block text-[var(--muted)]">Service account: {integration.google_calendar_configured ? "configured" : "not configured"}</small></label>
            <div><button className="btn-secondary" disabled={saving === "integrations"} onClick={() => void saveIntegrations()}>{saving === "integrations" ? <LoaderCircle className="animate-spin" size={17} /> : <Save size={17} />}{saving === "integrations" ? "Saving..." : "Save integrations"}</button></div>
          </div>
        </SettingsPanel>
      )}
    </ProfileLayout>
  );
}

function SettingsPanel({ icon, title, intro, children }: { icon: React.ReactNode; title: string; intro: string; children: React.ReactNode }) {
  return <section className="card overflow-hidden"><header className="flex items-start gap-4 border-b border-[var(--line)] bg-[linear-gradient(135deg,var(--blue-pale),#fff)] p-6"><span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-white text-[var(--blue-dark)] shadow-sm">{icon}</span><div><h2 className="text-xl font-bold">{title}</h2><p className="mt-1 text-sm text-[var(--muted)]">{intro}</p></div></header><div className="p-6">{children}</div></section>;
}

function SettingsGrid({ children }: { children: React.ReactNode }) {
  return <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">{children}</div>;
}

function SettingNumber({ label, prefix, suffix, value, onChange, min = 0, max, step = "1" }: { label: string; prefix?: string; suffix?: string; value: string | number; onChange: (value: string) => void; min?: number; max?: number; step?: string }) {
  return <label><span className="mb-2 block text-sm font-bold">{label}</span><span className="flex items-center overflow-hidden rounded-xl border border-[var(--line)] bg-white focus-within:border-[var(--blue-dark)] focus-within:ring-4 focus-within:ring-[var(--blue-pale)]">{prefix && <span className="pl-4 text-sm font-bold text-[var(--muted)]">{prefix}</span>}<input type="number" className="min-w-0 flex-1 bg-transparent px-3 py-3 outline-none" min={min} max={max} step={step} value={value ?? ""} onChange={(event) => onChange(event.target.value)} />{suffix && <span className="pr-4 text-xs font-bold text-[var(--muted)]">{suffix}</span>}</span></label>;
}
function ProfileLayout({
  title,
  intro,
  children,
}: {
  title: string;
  intro: string;
  children: React.ReactNode;
}) {
  return (
    <div className="mx-auto max-w-5xl">
      <div className="eyebrow">Profile & onboarding</div>
      <h1 className="display mt-2 text-4xl sm:text-5xl">{title}</h1>
      <p className="mt-3 max-w-2xl text-[var(--muted)]">{intro}</p>
      <div className="mt-7 grid gap-6">{children}</div>
    </div>
  );
}
function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="card p-6 sm:p-8">
      <h2 className="mb-6 text-xl font-bold">{title}</h2>
      {children}
    </section>
  );
}
function Grid({ children }: { children: React.ReactNode }) {
  return <div className="grid gap-5 sm:grid-cols-2">{children}</div>;
}
function Input({
  label,
  hint,
  onChange,
  ...props
}: Omit<React.InputHTMLAttributes<HTMLInputElement>, "onChange"> & {
  label: string;
  hint?: string;
  onChange: (v: string) => void;
}) {
  return (
    <label>
      <span className="mb-2 block text-sm font-bold">{label}</span>
      <input
        {...props}
        value={props.value ?? ""}
        className="field"
        onChange={(e) => onChange(e.target.value)}
      />
      {hint && (
        <small className="mt-2 block leading-5 text-[var(--muted)]">
          {hint}
        </small>
      )}
    </label>
  );
}
function Textarea({
  label,
  value,
  onChange,
}: {
  label: string;
  value?: string;
  onChange: (v: string) => void;
}) {
  return (
    <label>
      <span className="mb-2 block text-sm font-bold">{label}</span>
      <textarea
        className="field min-h-24 resize-y"
        value={value || ""}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  );
}
function Select({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value?: string;
  onChange: (v: string) => void;
  options: string[][];
}) {
  return (
    <label>
      <span className="mb-2 block text-sm font-bold">{label}</span>
      <select
        className="field"
        value={value || ""}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">Select</option>
        {options.map(([v, l]) => (
          <option key={v} value={v}>
            {l}
          </option>
        ))}
      </select>
    </label>
  );
}
function MultiSelect({
  label,
  hint,
  options,
  value,
  onChange,
}: {
  label: string;
  hint?: string;
  options: NamedOption[];
  value: number[];
  onChange: (value: number[]) => void;
}) {
  const selected = value.map(Number);
  return (
    <fieldset className="sm:col-span-2">
      <legend className="text-sm font-bold">{label}</legend>
      {hint && <p className="mt-1 text-sm text-[var(--muted)]">{hint}</p>}
      <div className="mt-3 grid gap-2 rounded-2xl border border-[var(--line)] p-4 sm:grid-cols-2 lg:grid-cols-3">
        {options.map((option) => (
          <label key={option.id} className="flex items-center gap-2 rounded-xl p-2 hover:bg-[var(--blue-pale)]">
            <input
              type="checkbox"
              checked={selected.includes(option.id)}
              onChange={(event) =>
                onChange(
                  event.target.checked
                    ? [...selected, option.id]
                    : selected.filter((id) => id !== option.id),
                )
              }
            />
            <span className="text-sm font-medium">{option.name}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
function YesNo({
  label,
  value,
  onChange,
}: {
  label: string;
  value?: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <Select
      label={label}
      value={value === undefined || value === null ? "" : value ? "yes" : "no"}
      onChange={(v) => onChange(v === "yes")}
      options={[
        ["yes", "Yes"],
        ["no", "No"],
      ]}
    />
  );
}
function Upload({
  label,
  current,
  approved,
  onFile,
}: {
  label: string;
  current?: string;
  approved?: boolean;
  onFile: (f: File) => void;
}) {
  return (
    <label
      className={`relative flex cursor-pointer items-center gap-3 rounded-2xl border p-4 transition ${approved ? "border-[#e4bd59] bg-[#fffaf0] shadow-[0_8px_24px_rgba(184,134,30,.10)]" : current ? "border-emerald-200 bg-emerald-50/40" : "border-[var(--line)]"}`}
    >
      <span
        className={`flex h-10 w-10 items-center justify-center rounded-xl ${approved ? "bg-[#f5d77f] text-[#76510a]" : current ? "bg-emerald-100 text-emerald-700" : "bg-[var(--blue-pale)]"}`}
      >
        {current ? <Check /> : <FileUp />}
      </span>
      <span className="flex-1">
        <b className="block">{label}</b>
        <small className="text-[var(--muted)]">
          {approved
            ? "Approved by My Nanny"
            : current
              ? "Uploaded · awaiting approval"
              : "PDF, JPG or PNG"}
        </small>
      </span>
      {current && (
        <span
          className={`rounded-full px-3 py-1 text-[10px] font-extrabold uppercase tracking-wider ${approved ? "bg-[#d6a72f] text-white shadow-sm" : "bg-emerald-100 text-emerald-800"}`}
        >
          {approved ? "Approved" : "Uploaded"}
        </span>
      )}
      <input
        className="hidden"
        type="file"
        accept=".pdf,image/*"
        onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])}
      />
    </label>
  );
}
function SaveBar({ status, onSave }: { status: string; onSave: () => void }) {
  return (
    <div className="sticky bottom-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[var(--line)] bg-white/95 p-4 shadow-xl backdrop-blur">
      <span className="text-sm text-[var(--muted)]">
        {status || "Changes are saved when you select Save."}
      </span>
      <button className="btn-primary" onClick={onSave}>
        <Save size={17} />
        Save profile
      </button>
    </div>
  );
}
function Loading() {
  return (
    <div className="flex min-h-96 items-center justify-center">
      <LoaderCircle className="animate-spin" />
    </div>
  );
}
