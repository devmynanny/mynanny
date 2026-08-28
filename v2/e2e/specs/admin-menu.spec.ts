import { expect, test, type Page } from "@playwright/test";

const adminDestinations = [
  ["Overview", "/dashboard"],
  ["Candidate review", "/review"],
  ["Users & records", "/users"],
  ["Bookings", "/bookings"],
  ["Finance", "/finance"],
  ["Refunds", "/refunds"],
  ["Safety centre", "/operations"],
  ["Communicator", "/communicator"],
  ["Audit logs", "/audit"],
  ["Trust configuration", "/trust"],
  ["Team access", "/team"],
  ["Settings", "/profile"],
] as const;

test("every admin menu destination loads without a server failure", async ({
  page,
}) => {
  const failures: string[] = [];

  page.on("response", (response) => {
    if (response.url().includes("/api/") && response.status() >= 500) {
      failures.push(`${response.status()} ${response.url()}`);
    }
  });
  page.on("pageerror", (error) => failures.push(`page error: ${error.message}`));

  await signInAsAdmin(page);

  for (const [label, pathname] of adminDestinations) {
    if (new URL(page.url()).pathname !== pathname) {
      await page.getByRole("link", { name: label, exact: true }).click();
    }

    await expect(page).toHaveURL(
      new RegExp(`${pathname.replace("/", "\\/")}(?:[?#]|$)`),
    );
    await expect(page.locator("main")).toBeVisible();
    await expect(
      page.getByText("Internal Server Error", { exact: true }),
    ).toHaveCount(0);
    await expect(
      page.getByText(/Application error: a client-side exception/i),
    ).toHaveCount(0);

    // Do not wait for network-idle because Communicator intentionally polls.
    await page.waitForTimeout(600);
  }

  expect(failures, failures.join("\n")).toEqual([]);
});

async function signInAsAdmin(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email address").fill("admin.e2e@example.test");
  await page.locator('input[type="password"]').fill("AdminE2E!234");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard/);
  await expect(
    page.getByRole("link", { name: "Overview", exact: true }),
  ).toBeVisible();
}
