import { expect, test } from "@playwright/test";

const formattedAddress =
  "21 Victoria Crescent, Louwlardia, Centurion, 0157, South Africa";

test("a parent GPS location is converted to an address before it is saved", async ({
  page,
}) => {
  await page.route("**/api/config/google-maps", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ google_maps_api_key: "e2e-browser-key" }),
    });
  });
  await page.route("https://maps.googleapis.com/maps/api/js?*", async (route) => {
    await route.fulfill({
      contentType: "application/javascript",
      body: `
        window.google = {
          maps: {
            places: {
              AutocompleteService: class {
                getPlacePredictions(_request, callback) {
                  callback([], "ZERO_RESULTS");
                }
              },
              PlacesServiceStatus: { OK: "OK", ZERO_RESULTS: "ZERO_RESULTS" }
            },
            Geocoder: class {
              geocode(request, callback) {
                callback([{
                  place_id: "e2e-parent-home",
                  formatted_address: ${JSON.stringify(formattedAddress)},
                  address_components: [
                    { long_name: "21", types: ["street_number"] },
                    { long_name: "Victoria Crescent", types: ["route"] },
                    { long_name: "Louwlardia", types: ["sublocality_level_1"] },
                    { long_name: "Centurion", types: ["locality"] },
                    { long_name: "Gauteng", types: ["administrative_area_level_1"] },
                    { long_name: "0157", types: ["postal_code"] },
                    { long_name: "South Africa", types: ["country"] }
                  ],
                  geometry: {
                    location: {
                      lat: () => request.location.lat,
                      lng: () => request.location.lng
                    }
                  }
                }], "OK");
              }
            },
            GeocoderStatus: { OK: "OK" }
          }
        };
      `,
    });
  });

  await page.goto("/signup?role=parent");
  await page.getByLabel("Full name").fill("Location Test Parent");
  await page.getByLabel("Mobile number").fill("+27821234567");
  await page
    .getByLabel("Email address")
    .fill("parent.location.e2e@example.com");
  await page.getByLabel("Password").fill("LocalE2E!234");
  await page.getByRole("button", { name: "Create my account" }).click();
  await expect(page).toHaveURL(/\/dashboard/);

  await page.goto("/profile");
  await page.getByRole("button", { name: "Use my current location" }).click();

  await expect(page.getByText(formattedAddress, { exact: true })).toBeVisible();
  await expect(
    page.getByText("Home address found and saved.", { exact: true }),
  ).toBeVisible();

  const firstSave = await page.evaluate(async () => {
    const response = await fetch("/api/parents/me/locations", {
      credentials: "include",
    });
    return response.json();
  });
  expect(firstSave).toHaveLength(1);
  expect(firstSave[0].formatted_address).toBe(formattedAddress);
  expect(firstSave[0].city).toBe("Centurion");

  await page.getByRole("button", { name: "Use my current location" }).click();
  await expect(
    page.getByText("Home address found and saved.", { exact: true }),
  ).toBeVisible();

  const secondSave = await page.evaluate(async () => {
    const response = await fetch("/api/parents/me/locations", {
      credentials: "include",
    });
    return response.json();
  });
  expect(secondSave).toHaveLength(1);
});
