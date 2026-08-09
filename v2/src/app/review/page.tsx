"use client";

import { AuthenticatedPage } from "@/components/authenticated-page";
import { apiJson } from "@/lib/api";
import {
  ArrowUpRight,
  AlertTriangle,
  BadgeCheck,
  Check,
  Clock3,
  LoaderCircle,
  MapPin,
  PlayCircle,
  Video,
  X,
} from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";

type Application = {
  nanny_id: number;
  user_id: number;
  name: string;
  email: string;
  profile_photo_url?: string | null;
  suburb?: string | null;
  city?: string | null;
  application_status: string;
  admin_reason?: string | null;
  approved: boolean;
  video_screening_complete: boolean;
  banking_complete: boolean;
  location_on_file: boolean;
};

type NannyProfileCompleteness = {
  profile_complete: boolean;
  profile_missing_fields: string[];
};

const fieldLabels: Record<string, string> = {
  profile_photo_url: "Profile photo",
  date_of_birth: "Date of birth",
  gender: "Gender",
  nationality: "Nationality",
  ethnicity: "Race / ethnicity",
  job_type: "Preferred job type",
  current_job_availability: "Current work availability",
  police_clearance_status: "Police clearance status",
  my_nanny_training_status: "My Nanny training status",
  has_own_car: "Transport details",
  has_own_kids: "Own children details",
  medical_conditions: "Medical conditions / medication",
  home_location: "Home location",
  languages: "Languages",
  has_drivers_license: "Driver's license details",
  own_kids_details: "Children details",
  studying_details: "Study details",
  sa_id_number: "South African ID number",
  sa_id_document_url: "South African ID document",
  passport_number: "Passport number",
  passport_expiry: "Passport expiry date",
  passport_document_url: "Passport document",
  permit_status: "Work permit status",
  work_permit_document_url: "Work permit document",
  work_permit_expiry: "Work permit expiry date",
};

function displayFieldName(field: string) {
  return (
    fieldLabels[field] ||
    field
      .replaceAll("_", " ")
      .replace(/\b\w/g, (character) => character.toUpperCase())
  );
}

export default function Review() {
  const [rows, setRows] = useState<Application[]>([]);
  const [selected, setSelected] = useState<Application | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [approvalWarning, setApprovalWarning] = useState<string[] | null>(null);
  const [approvalAcknowledged, setApprovalAcknowledged] = useState(false);
  async function load() {
    setLoading(true);
    try {
      const data = await apiJson<{ results: Application[] }>(
        "/admin/nannies/applications?status=pending",
      );
      setRows(data.results || []);
      setSelected(
        (current) =>
          data.results.find((row) => row.nanny_id === current?.nanny_id) ||
          data.results[0] ||
          null,
      );
    } catch (err) {
      setMessage(
        err instanceof Error ? err.message : "Unable to load applications.",
      );
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    apiJson<{ results: Application[] }>(
      "/admin/nannies/applications?status=pending",
    )
      .then((data) => {
        setRows(data.results || []);
        setSelected(data.results[0] || null);
      })
      .catch((err) =>
        setMessage(
          err instanceof Error ? err.message : "Unable to load applications.",
        ),
      )
      .finally(() => setLoading(false));
  }, []);
  async function update(status: "approved" | "hold" | "declined") {
    if (!selected) return;
    let reason = "";
    if (status !== "approved") {
      reason =
        window.prompt(
          status === "hold"
            ? "What information is still outstanding?"
            : "Why is this application being declined?",
        ) || "";
      if (!reason) return;
    }
    setBusy(true);
    setMessage("");
    try {
      await apiJson(`/admin/nannies/${selected.nanny_id}/application`, {
        method: "PATCH",
        body: JSON.stringify({ status, reason }),
      });
      setMessage(
        status === "approved"
          ? `${selected.name} is now approved.`
          : `Application moved to ${status}.`,
      );
      await load();
    } catch (err) {
      setMessage(
        err instanceof Error ? err.message : "Unable to update application.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function requestApproval() {
    if (!selected) return;
    setBusy(true);
    setMessage("");
    try {
      const profile = await apiJson<NannyProfileCompleteness>(
        `/admin/nannies/${selected.user_id}/profile`,
      );
      const missing = profile.profile_missing_fields || [];
      if (missing.length) {
        setApprovalAcknowledged(false);
        setApprovalWarning(missing);
        return;
      }
      await update("approved");
    } catch (err) {
      setMessage(
        err instanceof Error
          ? err.message
          : "Unable to check profile completeness.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function approveIncompleteProfile() {
    if (!approvalAcknowledged) return;
    setApprovalWarning(null);
    await update("approved");
  }
  return (
    <AuthenticatedPage>
      {(role) =>
        role !== "admin" ? (
          <div className="card mx-auto max-w-xl p-8 text-center">
            <h1 className="text-2xl font-bold">Team access only</h1>
          </div>
        ) : (
          <div className="mx-auto max-w-6xl">
            <div className="eyebrow">Candidate screening</div>
            <h1 className="display mt-2 text-4xl sm:text-5xl">Review queue.</h1>
            <p className="mt-3 text-[var(--muted)]">
              Only approve complete, video-screened profiles that are ready for
              parents.
            </p>
            {message && (
              <div
                role="status"
                className="mt-5 rounded-xl bg-[var(--blue-pale)] p-4 text-sm"
              >
                {message}
              </div>
            )}
            {loading ? (
              <div className="mt-12 flex justify-center">
                <LoaderCircle className="animate-spin" />
              </div>
            ) : (
              <div className="mt-7 grid gap-6 lg:grid-cols-[.72fr_1.28fr]">
                <aside className="card p-4">
                  <div className="mb-3 flex items-center justify-between px-2">
                    <span className="font-bold">
                      {rows.length} awaiting review
                    </span>
                    <Clock3 size={18} className="text-[var(--muted)]" />
                  </div>
                  {rows.length ? (
                    rows.map((application) => (
                      <button
                        key={application.nanny_id}
                        onClick={() => setSelected(application)}
                        className={`mb-2 flex w-full items-center gap-3 rounded-2xl p-3 text-left ${selected?.nanny_id === application.nanny_id ? "bg-[var(--blue-pale)]" : ""}`}
                      >
                        {application.profile_photo_url ? (
                          <Image
                            src={application.profile_photo_url}
                            alt=""
                            width={44}
                            height={44}
                            className="h-11 w-11 rounded-full object-cover"
                            unoptimized
                          />
                        ) : (
                          <div className="flex h-11 w-11 items-center justify-center rounded-full bg-white text-sm font-bold shadow">
                            {application.name[0]}
                          </div>
                        )}
                        <div className="min-w-0">
                          <div className="truncate font-bold">
                            {application.name}
                          </div>
                          <div className="text-xs text-[var(--muted)]">
                            {application.city || "Location pending"} ·{" "}
                            {application.video_screening_complete
                              ? "Video complete"
                              : "Video outstanding"}
                          </div>
                        </div>
                      </button>
                    ))
                  ) : (
                    <div className="p-6 text-center text-sm text-[var(--muted)]">
                      The review queue is clear.
                    </div>
                  )}
                </aside>
                {selected ? (
                  <section className="card overflow-hidden">
                    <div className="relative flex aspect-video items-center justify-center bg-[var(--ink)] text-white">
                      {selected.profile_photo_url ? (
                        <Image
                          src={selected.profile_photo_url}
                          alt={selected.name}
                          fill
                          className="object-cover opacity-40"
                          unoptimized
                        />
                      ) : null}
                      <div className="relative text-center">
                        {selected.video_screening_complete ? (
                          <>
                            <PlayCircle className="mx-auto" size={58} />
                            <span className="mt-2 block font-bold">
                              Video screening complete
                            </span>
                          </>
                        ) : (
                          <>
                            <Video
                              className="mx-auto text-amber-300"
                              size={52}
                            />
                            <span className="mt-2 block font-bold">
                              Video still outstanding
                            </span>
                          </>
                        )}
                      </div>
                    </div>
                    <div className="p-6">
                      <div className="flex flex-wrap items-start justify-between gap-4">
                        <div>
                          <h2 className="text-2xl font-bold">
                            {selected.name}
                          </h2>
                          <div className="mt-1 flex items-center gap-1 text-sm text-[var(--muted)]">
                            <MapPin size={14} />
                            {[selected.suburb, selected.city]
                              .filter(Boolean)
                              .join(", ") ||
                              (selected.location_on_file
                                ? "Coordinates on file"
                                : "Location not provided")}
                          </div>
                        </div>
                        <span className="pill">
                          <BadgeCheck
                            size={14}
                            className={
                              selected.video_screening_complete
                                ? "text-[var(--green)]"
                                : "text-amber-600"
                            }
                          />
                          {selected.video_screening_complete
                            ? "Video complete"
                            : "Video required"}
                        </span>
                      </div>
                      <div className="mt-6 grid gap-3 sm:grid-cols-2">
                        <div className="flex items-center gap-2 rounded-xl bg-[var(--blue-pale)] p-3 text-sm font-bold">
                          <Check size={16} className="text-[var(--green)]" />
                          Application submitted
                        </div>
                        <div
                          className={`flex items-center gap-2 rounded-xl p-3 text-sm font-bold ${selected.video_screening_complete ? "bg-[var(--blue-pale)]" : "bg-amber-50"}`}
                        >
                          {selected.video_screening_complete ? (
                            <Check size={16} className="text-[var(--green)]" />
                          ) : (
                            <X size={16} className="text-amber-700" />
                          )}
                          Video screening
                        </div>
                        <div
                          className={`flex items-center gap-2 rounded-xl p-3 text-sm font-bold ${selected.location_on_file ? "bg-[var(--blue-pale)]" : "bg-amber-50"}`}
                        >
                          {selected.location_on_file ? (
                            <Check size={16} className="text-[var(--green)]" />
                          ) : (
                            <X size={16} className="text-amber-700" />
                          )}
                          Location on file
                        </div>
                        <div
                          className={`flex items-center gap-2 rounded-xl p-3 text-sm font-bold ${selected.banking_complete ? "bg-[var(--blue-pale)]" : "bg-amber-50"}`}
                        >
                          {selected.banking_complete ? (
                            <Check size={16} className="text-[var(--green)]" />
                          ) : (
                            <X size={16} className="text-amber-700" />
                          )}
                          Payout details
                        </div>
                      </div>
                      <div className="mt-6 flex flex-wrap gap-3">
                        <Link
                          className="btn-secondary"
                          href={{
                            pathname: "/users",
                            query: { user: selected.user_id },
                          }}
                        >
                          <ArrowUpRight size={17} />
                          Open full profile
                        </Link>
                        <button
                          className="btn-primary"
                          disabled={
                            busy ||
                            !selected.video_screening_complete ||
                            !selected.location_on_file ||
                            !selected.banking_complete
                          }
                          onClick={requestApproval}
                        >
                          <Check size={17} />
                          Approve profile
                        </button>
                        <button
                          className="btn-secondary"
                          disabled={busy}
                          onClick={() => update("hold")}
                        >
                          Request information
                        </button>
                        <button
                          className="btn-quiet text-red-700"
                          disabled={busy}
                          onClick={() => update("declined")}
                        >
                          <X size={17} />
                          Decline
                        </button>
                      </div>
                      {!selected.video_screening_complete && (
                        <p className="mt-3 text-sm text-amber-800">
                          Approval is locked until the nanny completes video
                          screening.
                        </p>
                      )}
                      {selected.video_screening_complete &&
                        !selected.location_on_file && (
                          <p className="mt-3 text-sm text-amber-800">
                            Approval is locked until the nanny adds her home
                            location.
                          </p>
                        )}
                      {selected.video_screening_complete &&
                        selected.location_on_file &&
                        !selected.banking_complete && (
                          <p className="mt-3 text-sm text-amber-800">
                            Approval is locked until the nanny links her payout
                            account through Paystack.
                          </p>
                        )}
                    </div>
                  </section>
                ) : (
                  <section className="card flex min-h-96 items-center justify-center p-8 text-center text-[var(--muted)]">
                    Select an application to review.
                  </section>
                )}
              </div>
            )}
            {approvalWarning && selected && (
              <div
                className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 p-4 backdrop-blur-sm"
                role="dialog"
                aria-modal="true"
                aria-labelledby="incomplete-approval-title"
              >
                <div className="card w-full max-w-xl p-6 shadow-2xl sm:p-8">
                  <div className="flex items-start gap-4">
                    <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-amber-100 text-amber-700">
                      <AlertTriangle size={24} />
                    </div>
                    <div>
                      <div className="eyebrow text-amber-700">Incomplete profile</div>
                      <h2
                        id="incomplete-approval-title"
                        className="mt-1 text-2xl font-bold"
                      >
                        Approve {selected.name} anyway?
                      </h2>
                      <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
                        This candidate still has {approvalWarning.length}{" "}
                        outstanding {approvalWarning.length === 1 ? "item" : "items"}.
                        Approval may not make the profile visible to parents until
                        all mandatory requirements are met.
                      </p>
                    </div>
                  </div>
                  <div className="mt-5 max-h-56 overflow-y-auto rounded-2xl bg-amber-50 p-4">
                    <ul className="grid gap-2 text-sm">
                      {approvalWarning.map((field) => (
                        <li key={field} className="flex items-center gap-2">
                          <X size={15} className="shrink-0 text-amber-700" />
                          {displayFieldName(field)}
                        </li>
                      ))}
                    </ul>
                  </div>
                  <label className="mt-5 flex cursor-pointer items-start gap-3 rounded-2xl border border-[var(--line)] p-4 text-sm leading-5">
                    <input
                      type="checkbox"
                      checked={approvalAcknowledged}
                      onChange={(event) =>
                        setApprovalAcknowledged(event.target.checked)
                      }
                      className="mt-0.5 h-5 w-5 accent-[var(--blue)]"
                    />
                    <span>
                      I understand this profile is incomplete and want to approve
                      it anyway.
                    </span>
                  </label>
                  <div className="mt-6 flex flex-wrap justify-end gap-3">
                    <button
                      className="btn-secondary"
                      onClick={() => setApprovalWarning(null)}
                      disabled={busy}
                    >
                      Go back
                    </button>
                    <button
                      className="btn-primary"
                      onClick={approveIncompleteProfile}
                      disabled={busy || !approvalAcknowledged}
                    >
                      <Check size={17} />
                      Approve incomplete profile
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )
      }
    </AuthenticatedPage>
  );
}
