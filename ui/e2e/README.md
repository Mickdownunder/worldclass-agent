# UI E2E Tests (Playwright)

Run with:

```bash
cd ui && npm run test:e2e
```

- **Auth:** The dev server is started with a default test password (`e2etest`). To use your own, set `UI_PASSWORD_HASH` to the SHA-256 hex of your password and `E2E_PASSWORD` to that password when running tests.
- **Browser deps:** If Chromium fails to launch (e.g. `libnspr4.so` missing), run `npx playwright install-deps chromium` (may require sudo).
- **CI:** The Quality Gates workflow runs E2E in a separate job with `--with-deps` and the default hash above.
