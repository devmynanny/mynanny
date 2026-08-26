"use client";

import {
  GoogleAddressInput,
  type GoogleAddress,
} from "@/components/google-address-input";
import { apiJson } from "@/lib/api";
import { Check, LoaderCircle, LocateFixed, MapPin, Pencil } from "lucide-react";
import { useState } from "react";

type ReverseGeocodeResponse = GoogleAddress & {
  status?: string | null;
  error_message?: string | null;
};

type LocationStep = "gps" | "confirm-gps" | "manual" | "confirmed";

function currentPosition() {
  return new Promise<GeolocationPosition>((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error("Location services are not available on this device."));
      return;
    }
    navigator.geolocation.getCurrentPosition(resolve, reject, {
      enableHighAccuracy: true,
      timeout: 20_000,
      maximumAge: 0,
    });
  });
}

export function NannyLocationConfirmation({
  onConfirm,
  onReset,
}: {
  onConfirm: (address: GoogleAddress) => Promise<void> | void;
  onReset?: () => void;
}) {
  const [step, setStep] = useState<LocationStep>("gps");
  const [address, setAddress] = useState<GoogleAddress | null>(null);
  const [addressSearch, setAddressSearch] = useState("");
  const [locating, setLocating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  async function findWithGps() {
    onReset?.();
    setAddress(null);
    setAddressSearch("");
    setLocating(true);
    setMessage("Finding your location and matching it to an address...");
    try {
      const position = await currentPosition();
      const params = new URLSearchParams({
        lat: String(position.coords.latitude),
        lng: String(position.coords.longitude),
      });
      const result = await apiJson<ReverseGeocodeResponse>(
        `/geo/reverse?${params.toString()}`,
      );
      if (!result.formatted_address) {
        throw new Error(
          result.error_message || "Google could not identify this address.",
        );
      }
      setAddress(result);
      setStep("confirm-gps");
      setMessage("");
    } catch (error) {
      setStep("manual");
      const isLocationPermissionError =
        typeof error === "object" && error !== null && "code" in error;
      setMessage(
        isLocationPermissionError
          ? "We could not access your GPS location. Enter your home address manually below."
          : error instanceof Error
            ? `${error.message} Enter your home address manually below.`
            : "We could not find your address. Enter it manually below.",
      );
    } finally {
      setLocating(false);
    }
  }

  async function confirmAddress() {
    if (!address) return;
    setSaving(true);
    setMessage("Confirming your home address...");
    try {
      await onConfirm(address);
      setStep("confirmed");
      setMessage("Home address confirmed.");
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Unable to confirm your address.",
      );
    } finally {
      setSaving(false);
    }
  }

  function useManualAddress() {
    onReset?.();
    setAddress(null);
    setAddressSearch("");
    setStep("manual");
    setMessage("Enter your home address and choose it from the Google suggestions.");
  }

  if (step === "confirmed" && address) {
    return (
      <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5">
        <div className="flex gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-white text-emerald-700 shadow-sm">
            <Check size={21} />
          </span>
          <div>
            <div className="font-extrabold text-emerald-950">
              Home address confirmed
            </div>
            <p className="mt-1 leading-6 text-emerald-900">
              {address.formatted_address}
            </p>
          </div>
        </div>
        <button
          type="button"
          className="btn-secondary mt-4 !min-h-10"
          onClick={() => {
            onReset?.();
            setAddress(null);
            setStep("gps");
            setMessage("");
          }}
        >
          <LocateFixed size={17} />
          Check a different location
        </button>
      </div>
    );
  }

  return (
    <div className="grid gap-4 rounded-2xl border border-[var(--line)] bg-white p-5">
      {step === "gps" && (
        <>
          <div className="flex gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[var(--blue-pale)] text-[var(--blue)]">
              <LocateFixed size={21} />
            </span>
            <div>
              <div className="font-extrabold">Confirm where you live</div>
              <p className="mt-1 text-sm leading-6 text-[var(--muted)]">
                Start with your device location. We will show the matching
                address before anything is saved.
              </p>
            </div>
          </div>
          <button
            type="button"
            className="btn-primary w-full sm:w-fit"
            disabled={locating}
            onClick={() => void findWithGps()}
          >
            {locating ? (
              <LoaderCircle className="animate-spin" size={18} />
            ) : (
              <LocateFixed size={18} />
            )}
            {locating ? "Finding my address..." : "Use GPS to find my address"}
          </button>
        </>
      )}

      {step === "confirm-gps" && address && (
        <>
          <div className="rounded-2xl bg-[var(--blue-pale)] p-5">
            <div className="flex gap-3">
              <MapPin className="mt-0.5 shrink-0 text-[var(--blue)]" size={22} />
              <div>
                <div className="text-sm font-bold uppercase tracking-wide text-[var(--muted)]">
                  Google found this address
                </div>
                <p className="mt-2 text-lg font-extrabold leading-7">
                  {address.formatted_address}
                </p>
                <p className="mt-2 text-sm text-[var(--muted)]">
                  Do you live at this address?
                </p>
              </div>
            </div>
          </div>
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              className="btn-primary"
              disabled={saving}
              onClick={() => void confirmAddress()}
            >
              {saving ? (
                <LoaderCircle className="animate-spin" size={18} />
              ) : (
                <Check size={18} />
              )}
              {saving ? "Confirming..." : "Yes, I live here"}
            </button>
            <button
              type="button"
              className="btn-secondary"
              disabled={saving}
              onClick={useManualAddress}
            >
              <Pencil size={17} />
              No, enter address manually
            </button>
          </div>
        </>
      )}

      {step === "manual" && (
        <>
          <div>
            <div className="font-extrabold">Enter your correct home address</div>
            <p className="mt-1 text-sm leading-6 text-[var(--muted)]">
              Start typing, then choose the full address from Google.
            </p>
          </div>
          <GoogleAddressInput
            label="Home address"
            value={addressSearch}
            onChange={(value) => {
              setAddressSearch(value);
              setAddress(null);
            }}
            onSelected={(selectedAddress) => {
              setAddressSearch(selectedAddress.formatted_address);
              setAddress(selectedAddress);
              setMessage("Is this your correct home address? Confirm it below.");
            }}
          />
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              className="btn-primary"
              disabled={!address || saving}
              onClick={() => void confirmAddress()}
            >
              {saving ? (
                <LoaderCircle className="animate-spin" size={18} />
              ) : (
                <Check size={18} />
              )}
              {saving ? "Confirming..." : "Confirm this address"}
            </button>
            <button
              type="button"
              className="btn-secondary"
              disabled={saving}
              onClick={() => {
                onReset?.();
                setAddress(null);
                setAddressSearch("");
                setStep("gps");
                setMessage("");
              }}
            >
              <LocateFixed size={17} />
              Try GPS again
            </button>
          </div>
        </>
      )}

      {message && (
        <p
          role="status"
          className="rounded-xl bg-[var(--blue-pale)] px-4 py-3 text-sm leading-6 text-[var(--blue-dark)]"
        >
          {message}
        </p>
      )}
      <p className="text-xs leading-5 text-[var(--muted)]">
        Your exact home address is used for distance matching and is not shown
        to parents.
      </p>
    </div>
  );
}
