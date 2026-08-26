import { expect, test } from "@playwright/test";

test.describe.configure({ mode: "serial" });

const questions = [
  "Tell families a little about yourself.",
  "Why do you enjoy caring for children?",
  "How would you handle a difficult or unexpected situation?",
  "What does a great day with a child look like to you?",
];

test("nanny details flow through video submission into profile completion", async ({
  page,
}) => {
  await page.route("**/api/geo/reverse?*", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        place_id: "e2e-samrand-place",
        formatted_address: "23 Sterling Road, Samrand, Midrand, 1682, South Africa",
        street: "23 Sterling Road",
        suburb: "Samrand",
        city: "Midrand",
        province: "Gauteng",
        postal_code: "1682",
        country: "South Africa",
        lat: -25.998,
        lng: 28.126,
      }),
    });
  });
  await page.goto("/signup?role=nanny");

  await page.getByLabel("Full name").fill("Veronica Flow Test");
  await page.getByLabel("Mobile number").fill("+27821234567");
  await page
    .getByLabel("Email address")
    .fill("veronica.flow@example.com");
  await page.getByLabel("Password").fill("LocalE2E!234");
  await page.getByRole("button", { name: "Create my nanny account" }).click();

  await expect(
    page.getByRole("heading", { name: "Complete your nanny profile." }),
  ).toBeVisible();

  await page.getByLabel("Alternative phone").fill("+27829876543");
  await page.getByLabel("Nationality").selectOption("South African");
  await page.getByLabel("Gender").selectOption("female");
  await page.getByLabel("Race").selectOption("black");
  await page.getByLabel("South African ID number").fill("9001015800088");
  await page.getByLabel("Preferred job type").selectOption("both");
  await page.getByLabel("Police clearance").selectOption("yes");
  await page.getByLabel("Do you have your own car?").selectOption("no");
  await page
    .getByLabel("Do you have a driver’s license?")
    .selectOption("no");
  await page.getByLabel("Do you have children?").selectOption("no");
  await page
    .getByLabel("My Nanny training completed?")
    .selectOption("yes");

  await page
    .getByRole("button", { name: "Use GPS to find my address" })
    .click();
  await expect(
    page.getByText(
      "23 Sterling Road, Samrand, Midrand, 1682, South Africa",
      { exact: true },
    ),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "No, enter address manually" })
    .click();
  await expect(page.getByLabel("Home address")).toBeVisible();
  await page.getByRole("button", { name: "Try GPS again" }).click();
  await page
    .getByRole("button", { name: "Use GPS to find my address" })
    .click();
  await expect(
    page.getByText(
      "23 Sterling Road, Samrand, Midrand, 1682, South Africa",
      { exact: true },
    ),
  ).toBeVisible();
  await page.getByRole("button", { name: "Yes, I live here" }).click();
  await expect(
    page.getByText("Home address confirmed", { exact: true }),
  ).toBeVisible();

  await page
    .getByRole("button", { name: "Save location and continue" })
    .click();
  await expect(page).toHaveURL(/\/interview\?welcome=nanny/);

  const application = await page.evaluate(async () => {
    const response = await fetch("/api/nannies/me/profile", {
      credentials: "include",
    });
    return response.json();
  });
  expect(application.gender).toBe("female");
  expect(application.ethnicity).toBe("black");
  expect(application.nationality).toBe("South African");
  expect(application.lat).toBeCloseTo(-25.998, 3);
  expect(application.lng).toBeCloseTo(28.126, 3);

  await recordAnswer(page);
  await page.getByRole("button", { name: "Record again" }).click();
  await expect(page.getByText(/Recording ·/)).toBeVisible();
  await page.waitForTimeout(2_000);
  await page.getByRole("button", { name: "Stop and save" }).click();
  await assertReplayIsReady(page);

  for (const question of questions.slice(1)) {
    await page.getByRole("button", { name: question }).click();
    await recordAnswer(page);
  }

  await expect(
    page.getByText("All four answers are ready", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Submit interview" }).click();
  await expect(
    page.getByText(/Taking you to your profile to complete your photo/),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/profile\?from=interview/, {
    timeout: 10_000,
  });

  await expect(
    page.getByText("Interview successfully submitted", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", {
      name: "Complete your photo and required documents",
    }),
  ).toBeVisible();

  const finalState = await page.evaluate(async () => {
    const [profileResponse, screeningResponse] = await Promise.all([
      fetch("/api/nannies/me/profile", { credentials: "include" }),
      fetch("/api/nannies/me/video-screening", { credentials: "include" }),
    ]);
    return {
      profile: await profileResponse.json(),
      screening: await screeningResponse.json(),
    };
  });
  expect(finalState.profile.gender).toBe("female");
  expect(finalState.profile.ethnicity).toBe("black");
  expect(finalState.screening.video_screening_complete).toBe(true);
  expect(finalState.screening.clips).toHaveLength(4);
});

test("admin sees the submitted candidate and cannot approve an incomplete payout profile", async ({
  page,
}) => {
  await page.goto("/login");
  await page.getByLabel("Email address").fill("admin.e2e@example.test");
  await page.locator('input[type="password"]').fill("AdminE2E!234");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard/);

  await page.goto("/review");
  await page
    .getByRole("button", { name: /Veronica Flow Test/ })
    .click();

  await expect(
    page.getByText("Video screening complete", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Location on file", { exact: true })).toBeVisible();
  await expect(page.getByText("Payout details", { exact: true })).toBeVisible();
  await expect(
    page.getByText(
      "Approval is locked until the nanny links her payout account through Paystack.",
      { exact: true },
    ),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Approve profile" }),
  ).toBeDisabled();

  const bypassAttempt = await page.evaluate(async () => {
    const csrf = document.cookie
      .split("; ")
      .find((item) => item.startsWith("csrf_token="))
      ?.split("=")
      .slice(1)
      .join("=");
    const applicationsResponse = await fetch(
      "/api/admin/nannies/applications?status=pending",
      { credentials: "include" },
    );
    const applications = await applicationsResponse.json();
    const candidate = applications.results.find(
      (item: { name: string }) => item.name === "Veronica Flow Test",
    );
    const response = await fetch(
      `/api/admin/nannies/${candidate.nanny_id}/application`,
      {
        method: "PATCH",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": decodeURIComponent(csrf || ""),
        },
        body: JSON.stringify({ status: "approved", reason: "" }),
      },
    );
    return { status: response.status, body: await response.json() };
  });

  expect(bypassAttempt.status).toBeGreaterThanOrEqual(400);
  expect(JSON.stringify(bypassAttempt.body)).toContain("payout");
});

async function recordAnswer(page: import("@playwright/test").Page) {
  await page.getByRole("button", { name: "Start recording" }).click();
  await expect(page.getByText(/Recording ·/)).toBeVisible();
  await page.waitForTimeout(2_000);
  await page.getByRole("button", { name: "Stop and save" }).click();
  await assertReplayIsReady(page);
}

async function assertReplayIsReady(page: import("@playwright/test").Page) {
  await expect(
    page.getByText("Answer saved. You can replay or record it again."),
  ).toBeVisible({ timeout: 30_000 });
  const replay = page.locator("video[controls]");
  await expect(replay).toBeVisible();
  await expect.poll(() => replay.getAttribute("src")).toMatch(/^blob:/);
}
