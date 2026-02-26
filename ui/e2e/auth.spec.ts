/**
 * E2E: Login flow.
 * For tests to pass, run the app with UI_PASSWORD_HASH set to the SHA-256 hex of the test password.
 * Example (password "e2etest"): UI_PASSWORD_HASH=37a97310cedfe6ae001033c2b9832f6c9722b3337d3aba2ee3bb4b71756a9d72
 */
import { test, expect } from "@playwright/test";

const E2E_PASSWORD = process.env.E2E_PASSWORD ?? "e2etest";

test.describe("Login", () => {
  test("unauthenticated visit to / redirects to /login", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByRole("heading", { name: /Operator/i })).toBeVisible();
  });

  test("wrong password shows error", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel(/Passwort/i).fill("wrong-password");
    await page.getByRole("button", { name: /Anmelden|Einloggen|Submit/i }).click();
    await expect(page.getByText(/fehlgeschlagen|Anmeldung|error|Falsch/i)).toBeVisible({ timeout: 5000 });
    await expect(page).toHaveURL("/login");
  });

  test("correct password redirects to dashboard", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel(/Passwort/i).fill(E2E_PASSWORD);
    await page.getByRole("button", { name: /Anmelden|Einloggen|Submit/i }).click();
    await expect(page).toHaveURL(/\/(research)?(\?.*)?$/, { timeout: 10000 });
    await expect(page).not.toHaveURL("/login");
  });
});
