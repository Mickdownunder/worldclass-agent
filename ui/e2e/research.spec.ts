/**
 * E2E: Research projects — create, list, detail, cancel, delete.
 * Requires UI_PASSWORD_HASH set to SHA-256 hex of E2E_PASSWORD (default "e2etest").
 */
import { test, expect } from "@playwright/test";

const E2E_PASSWORD = process.env.E2E_PASSWORD ?? "e2etest";

async function login(page: import("@playwright/test").Page) {
  await page.goto("/login");
  await page.getByLabel(/Passwort/i).fill(E2E_PASSWORD);
  await page.getByRole("button", { name: /Anmelden|Einloggen|Submit/i }).click();
  await expect(page).not.toHaveURL("/login", { timeout: 10000 });
}

test.describe("Research", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test("research list shows header and new project form", async ({ page }) => {
    await page.goto("/research");
    await expect(page.getByRole("heading", { name: /Research Projects/i })).toBeVisible();
    await expect(page.getByText(/New Research Project/i)).toBeVisible();
    await expect(page.getByRole("button", { name: /Forschung starten/i })).toBeVisible();
  });

  test("create project: empty submit shows validation error", async ({ page }) => {
    await page.goto("/research");
    await page.getByRole("button", { name: /Forschung starten/i }).click();
    await expect(page.getByText(/Bitte eine Forschungsfrage eingeben/i)).toBeVisible({ timeout: 3000 });
  });

  test("create project: with question submits and list updates", async ({ page }) => {
    await page.goto("/research");
    const question = `E2E Test ${Date.now()} – delete me`;
    await page.getByLabel(/Was willst du erforschen|Forschungsfrage/i).fill(question);
    await page.getByRole("button", { name: /Forschung starten/i }).click();
    await expect(page.getByText(/Init läuft|bitte kurz warten/i).or(page.getByText(question))).toBeVisible({ timeout: 15000 });
    await expect(page.getByText(question)).toBeVisible({ timeout: 15000 });
  });

  test("project detail: status and actions visible", async ({ page }) => {
    await page.goto("/research");
    const projectLink = page.locator('a[href^="/research/"]').filter({ hasNot: page.getByText("Research Projects") }).first();
    const count = await projectLink.count();
    if (count === 0) {
      test.skip();
      return;
    }
    await projectLink.click();
    await expect(page).toHaveURL(/\/research\/[^/]+/);
    await expect(page.getByText(/Research Projects/)).toBeVisible();
    await expect(page.getByRole("button", { name: /Projekt löschen/i })).toBeVisible();
  });

  test("delete project: confirm dialog and redirect", async ({ page }) => {
    await page.goto("/research");
    const questionText = /E2E Test \d+ – delete me/;
    const row = page.locator('a[href^="/research/"]').filter({ hasText: questionText }).first();
    const rowCount = await row.count();
    if (rowCount === 0) {
      test.skip();
      return;
    }
    await row.click();
    await expect(page).toHaveURL(/\/research\/[^/]+/);
    page.on("dialog", (d) => d.accept());
    await page.getByRole("button", { name: /Projekt löschen/i }).click();
    await expect(page).toHaveURL(/\/research\/?(\?.*)?$/, { timeout: 10000 });
  });
});
