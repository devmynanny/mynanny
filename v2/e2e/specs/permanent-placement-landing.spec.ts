import { expect, test } from "@playwright/test";

test("landing page presents short-term, Self-Match and Concierge care", async ({
  page,
}) => {
  await page.goto("/");

  await expect(
    page.getByRole("heading", {
      name: "One trusted place. Three ways to find care.",
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Short-term bookings" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Lead your own search" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Let Mariette manage it" }),
  ).toBeVisible();

  await expect(page.getByRole("link", { name: /Start Self-Match/ })).toHaveAttribute(
    "href",
    "/signup?role=parent&next=%2Fplacements",
  );
  await expect(
    page.getByRole("link", { name: /Request Concierge support/ }),
  ).toHaveAttribute("href", "/signup?role=parent&next=%2Fplacements");
});

test("permanent placement destination survives signup and login", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("link", { name: /Start Self-Match/ }).click();

  await expect(page).toHaveURL(/\/signup\?role=parent&next=%2Fplacements$/);
  await expect(
    page.getByRole("heading", { name: "Find the right nanny for the long term." }),
  ).toBeVisible();

  await page.getByRole("link", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/login\?next=%2Fplacements$/);
  await expect(page.getByRole("link", { name: "Create an account" })).toHaveAttribute(
    "href",
    "/signup?role=parent&next=%2Fplacements",
  );
});

test("direct permanent placement access returns signed-out users to the same journey", async ({
  page,
}) => {
  await page.goto("/placements");
  await expect(page).toHaveURL(/\/login\?next=%2Fplacements$/);
});
