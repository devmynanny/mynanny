"use client";

import { apiJson } from "@/lib/api";
import { LoaderCircle, MapPin } from "lucide-react";
import { useEffect, useRef, useState } from "react";

export type GoogleAddress = {
  place_id: string;
  formatted_address: string;
  street: string;
  suburb: string;
  city: string;
  province: string;
  postal_code: string;
  country: string;
  lat: number;
  lng: number;
};

type AddressSuggestion = { place_id: string; description: string };
type GooglePrediction = { place_id: string; description: string };
type GoogleGeocoderResult = {
  place_id: string;
  formatted_address: string;
  address_components: { long_name: string; types: string[] }[];
  geometry: { location: { lat: () => number; lng: () => number } };
};
type GooglePlacesWindow = Window & {
  google?: {
    maps: {
      places: {
        AutocompleteService: new () => {
          getPlacePredictions: (
            request: Record<string, unknown>,
            callback: (
              results: GooglePrediction[] | null,
              status: string,
            ) => void,
          ) => void;
        };
        PlacesServiceStatus: { OK: string; ZERO_RESULTS: string };
      };
      Geocoder: new () => {
        geocode: (
          request:
            | { placeId: string }
            | { location: { lat: number; lng: number } },
          callback: (
            results: GoogleGeocoderResult[] | null,
            status: string,
          ) => void,
        ) => void;
      };
      GeocoderStatus: { OK: string };
    };
  };
};

let googlePlacesLoader: Promise<void> | null = null;

async function loadGooglePlacesServices() {
  const browserWindow = window as GooglePlacesWindow;
  if (browserWindow.google?.maps?.places) return;
  if (googlePlacesLoader) return googlePlacesLoader;

  googlePlacesLoader = apiJson<{ google_maps_api_key?: string | null }>(
    "/config/google-maps",
  )
    .then((config) => {
      const apiKey = config.google_maps_api_key;
      if (!apiKey) {
        throw new Error("Google Maps is not configured.");
      }
      return new Promise<void>((resolve, reject) => {
        const existing = document.querySelector<HTMLScriptElement>(
          'script[data-my-nanny-google-places="true"]',
        );
        if (existing) {
          existing.addEventListener("load", () => resolve(), { once: true });
          existing.addEventListener(
            "error",
            () => reject(new Error("Unable to load Google Places.")),
            { once: true },
          );
          return;
        }

        const script = document.createElement("script");
        script.dataset.myNannyGooglePlaces = "true";
        script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(apiKey)}&libraries=places`;
        script.async = true;
        script.onload = () => resolve();
        script.onerror = () =>
          reject(new Error("Unable to load Google Places."));
        document.head.appendChild(script);
      });
    })
    .catch((error) => {
      googlePlacesLoader = null;
      throw error;
    });

  return googlePlacesLoader;
}

function addressFromGeocoderResult(
  result: GoogleGeocoderResult,
  placeId = result.place_id,
): GoogleAddress {
  const component = (...types: string[]) => {
    for (const type of types) {
      const match = result.address_components.find((item) =>
        item.types.includes(type),
      );
      if (match) return match.long_name;
    }
    return "";
  };
  const street = [component("street_number"), component("route")]
    .filter(Boolean)
    .join(" ");

  return {
    place_id: placeId,
    formatted_address: result.formatted_address,
    street,
    suburb: component(
      "sublocality_level_1",
      "sublocality",
      "neighborhood",
    ),
    city: component("locality", "administrative_area_level_2"),
    province: component("administrative_area_level_1"),
    postal_code: component("postal_code"),
    country: component("country"),
    lat: result.geometry.location.lat(),
    lng: result.geometry.location.lng(),
  };
}

export async function reverseGeocodeCoordinates(
  lat: number,
  lng: number,
): Promise<GoogleAddress> {
  await loadGooglePlacesServices();
  const maps = (window as GooglePlacesWindow).google?.maps;
  if (!maps) throw new Error("Google Maps is unavailable.");

  const result = await new Promise<GoogleGeocoderResult>((resolve, reject) => {
    new maps.Geocoder().geocode(
      { location: { lat, lng } },
      (results, status) => {
        if (status === maps.GeocoderStatus.OK && results?.[0]) {
          resolve(results[0]);
        } else {
          reject(
            new Error(
              "We found your location but could not identify its street address. Please enter the address manually.",
            ),
          );
        }
      },
    );
  });

  return addressFromGeocoderResult(result);
}

export function GoogleAddressInput({
  value,
  onChange,
  onSelected,
  label = "Address search",
}: {
  value: string;
  onChange: (value: string) => void;
  onSelected: (address: GoogleAddress) => void;
  label?: string;
}) {
  const suppressSearch = useRef(false);
  const [suggestions, setSuggestions] = useState<AddressSuggestion[]>([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [mapsStatus, setMapsStatus] = useState("");

  useEffect(() => {
    if (suppressSearch.current) {
      suppressSearch.current = false;
      return;
    }
    const query = value.trim();
    if (query.length < 3) {
      return;
    }

    let active = true;
    const timer = window.setTimeout(() => {
      setLoadingSuggestions(true);
      loadGooglePlacesServices()
        .then(() => {
          const maps = (window as GooglePlacesWindow).google?.maps;
          if (!maps) throw new Error("Google Places is unavailable.");
          new maps.places.AutocompleteService().getPlacePredictions(
            {
              input: query,
              componentRestrictions: { country: "za" },
              types: ["address"],
            },
            (results, status) => {
              if (!active) return;
              if (status === maps.places.PlacesServiceStatus.OK) {
                setSuggestions(results || []);
                setMapsStatus("");
              } else if (
                status === maps.places.PlacesServiceStatus.ZERO_RESULTS
              ) {
                setSuggestions([]);
                setMapsStatus("No matching South African address found.");
              } else {
                setMapsStatus("Google address search is unavailable.");
              }
              setLoadingSuggestions(false);
            },
          );
        })
        .catch((error) => {
          if (!active) return;
          setLoadingSuggestions(false);
          setMapsStatus(
            error instanceof Error
              ? error.message
              : "Google address search is unavailable.",
          );
        });
    }, 300);

    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [value]);

  async function chooseSuggestion(suggestion: AddressSuggestion) {
    setMapsStatus("Confirming address...");
    try {
      await loadGooglePlacesServices();
      const maps = (window as GooglePlacesWindow).google?.maps;
      if (!maps) throw new Error("Google Places is unavailable.");
      const result = await new Promise<GoogleGeocoderResult>(
        (resolve, reject) => {
          new maps.Geocoder().geocode(
            { placeId: suggestion.place_id },
            (results, status) => {
              if (status === maps.GeocoderStatus.OK && results?.[0]) {
                resolve(results[0]);
              } else {
                reject(new Error("Unable to confirm this Google address."));
              }
            },
          );
        },
      );
      const address = addressFromGeocoderResult(result, suggestion.place_id);
      suppressSearch.current = true;
      onChange(address.formatted_address);
      onSelected(address);
      setSuggestions([]);
      setMapsStatus("Google address selected and ready to save.");
    } catch (error) {
      setMapsStatus(
        error instanceof Error
          ? error.message
          : "Unable to confirm this address.",
      );
    }
  }

  return (
    <label className="block">
      <span className="mb-2 block text-sm font-bold">{label}</span>
      <div className="relative">
        <MapPin
          size={18}
          className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[var(--blue)]"
        />
        <input
          className="field !pl-11"
          value={value}
          onChange={(event) => {
            const nextValue = event.target.value;
            if (nextValue.trim().length < 3) {
              setSuggestions([]);
              setMapsStatus("");
            }
            onChange(nextValue);
          }}
          placeholder="Start typing a South African address"
          autoComplete="off"
        />
        {(suggestions.length > 0 || loadingSuggestions) && (
          <div className="absolute left-0 right-0 top-[calc(100%+8px)] z-30 overflow-hidden rounded-2xl border border-[var(--line)] bg-white shadow-xl">
            {loadingSuggestions && !suggestions.length ? (
              <div className="flex items-center gap-2 p-4 text-sm text-[var(--muted)]">
                <LoaderCircle size={16} className="animate-spin" /> Searching
                Google...
              </div>
            ) : (
              suggestions.map((suggestion) => (
                <button
                  type="button"
                  key={suggestion.place_id}
                  className="flex w-full items-start gap-3 border-b border-[var(--line)] px-4 py-3 text-left text-sm last:border-b-0 hover:bg-[var(--blue-pale)]"
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => void chooseSuggestion(suggestion)}
                >
                  <MapPin
                    size={16}
                    className="mt-0.5 shrink-0 text-[var(--blue)]"
                  />
                  <span>{suggestion.description}</span>
                </button>
              ))
            )}
          </div>
        )}
      </div>
      {mapsStatus && (
        <span className="mt-2 block text-xs text-[var(--muted)]">
          {mapsStatus}
        </span>
      )}
    </label>
  );
}
