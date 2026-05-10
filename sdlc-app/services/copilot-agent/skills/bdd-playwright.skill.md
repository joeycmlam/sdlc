---
id: bdd-playwright
name: bdd-playwright
description: 'BDD test scenarios with Playwright using playwright-bdd. Use when: writing Gherkin feature files for Playwright end-to-end tests, implementing Given/When/Then step definitions with Playwright fixtures, configuring playwright.config.ts with BDD, generating test code from feature files, using Page Object Models in BDD steps, tagging Playwright BDD scenarios, or debugging feature-to-step mapping in Playwright BDD projects.'
argument-hint: 'Feature name or UI flow to implement with Playwright BDD'
---

# BDD with Playwright (playwright-bdd)

## When to Use
- End-to-end browser tests written in Gherkin
- Step definitions that use Playwright's `page`, `browser`, and fixture APIs
- Combining Page Object Model (POM) with BDD step definitions
- Running Playwright reports alongside Gherkin scenario output

## Prerequisites

```bash
npm install --save-dev @playwright/test playwright-bdd
npx playwright install
```

---

## Project Layout

```
features/
├── login.feature                   # Gherkin feature files
└── steps/
    ├── login.steps.ts              # Step definitions (Playwright fixtures)
    └── fixtures.ts                 # Custom fixture extensions
playwright.config.ts                # Playwright + BDD configuration
.features-gen/                      # Auto-generated test files (gitignore this)
```

Add `.features-gen/` to `.gitignore` — these files are regenerated on each run.

---

## Procedure

### Step 1 — Write the Feature File

Create `features/<feature>.feature`:

```gherkin
Feature: User Login
  As a registered user
  I want to log in with my credentials
  So that I can access my account

  Background:
    Given I am on the login page

  @smoke
  Scenario: Successful login with valid credentials
    When I enter username "alice@example.com" and password "secret"
    And I click the login button
    Then I should be redirected to the dashboard
    And I should see "Hello, Alice"

  Scenario: Login fails with incorrect password
    When I enter username "alice@example.com" and password "wrong"
    And I click the login button
    Then I should see an error "Invalid credentials"

  Scenario Outline: Login fails with invalid email
    When I enter username "<email>" and password "secret"
    And I click the login button
    Then I should see a validation error "<error>"

    Examples:
      | email        | error                      |
      | notanemail   | Please enter a valid email |
      | @missing.com | Please enter a valid email |
```

---

### Step 2 — Configure playwright.config.ts

```typescript
import { defineConfig } from "@playwright/test";
import { defineBddConfig } from "playwright-bdd";

const testDir = defineBddConfig({
  features: "features/**/*.feature",
  steps: "features/steps/**/*.ts",
});

export default defineConfig({
  testDir,
  use: {
    baseURL: process.env.BASE_URL ?? "http://localhost:3000",
    headless: true,
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  reporter: [
    ["html", { outputFolder: "playwright-report" }],
    ["list"],
  ],
});
```

---

### Step 3 — Write Step Definitions

`features/steps/login.steps.ts`:

```typescript
import { createBdd } from "playwright-bdd";
import { expect } from "@playwright/test";
import { test } from "./fixtures";  // use extended fixtures if any

const { Given, When, Then } = createBdd(test);

Given("I am on the login page", async ({ page }) => {
  await page.goto("/login");
});

When(
  "I enter username {string} and password {string}",
  async ({ page }, username: string, password: string) => {
    await page.fill('[name="username"]', username);
    await page.fill('[name="password"]', password);
  }
);

When("I click the login button", async ({ page }) => {
  await page.click('[type="submit"]');
});

Then("I should be redirected to the dashboard", async ({ page }) => {
  await expect(page).toHaveURL(/\/dashboard/);
});

Then("I should see {string}", async ({ page }, text: string) => {
  await expect(page.locator("body")).toContainText(text);
});

Then(
  "I should see an error {string}",
  async ({ page }, message: string) => {
    await expect(page.locator(".error-message")).toHaveText(message);
  }
);

Then(
  "I should see a validation error {string}",
  async ({ page }, error: string) => {
    await expect(page.locator(".validation-error")).toHaveText(error);
  }
);
```

> Steps receive Playwright fixtures as the **first argument** (destructured), followed by Gherkin parameters. Do NOT use `this` — playwright-bdd uses fixture injection, not World objects.

---

### Step 4 — Extend Fixtures (Optional)

`features/steps/fixtures.ts`:

```typescript
import { test as base } from "@playwright/test";
import { createBdd } from "playwright-bdd";

// Extend with a Page Object or shared state
export const test = base.extend<{ loginPage: LoginPage }>({
  loginPage: async ({ page }, use) => {
    const loginPage = new LoginPage(page);
    await use(loginPage);
  },
});

export const { Given, When, Then } = createBdd(test);
```

Use the exported `Given/When/Then` from `fixtures.ts` in all step files to get access to custom fixtures.

---

### Step 5 — Generate and Run Tests

playwright-bdd generates intermediate test files before running:

```bash
# Generate .features-gen/ files and run all tests
npx bddgen && npx playwright test

# Run only smoke-tagged scenarios
npx bddgen && npx playwright test --grep @smoke

# Run a specific feature
npx bddgen && npx playwright test --grep "User Login"

# Run headed (visible browser)
npx bddgen && npx playwright test --headed

# View HTML report
npx playwright show-report
```

Add to `package.json` for convenience:

```json
{
  "scripts": {
    "test:bdd": "bddgen && playwright test",
    "test:smoke": "bddgen && playwright test --grep @smoke",
    "report": "playwright show-report"
  }
}
```

---

### Step 6 — Use Page Object Model with BDD

```typescript
// features/pages/login.page.ts
import { Page } from "@playwright/test";

export class LoginPage {
  constructor(private page: Page) {}

  async goto() {
    await this.page.goto("/login");
  }

  async login(username: string, password: string) {
    await this.page.fill('[name="username"]', username);
    await this.page.fill('[name="password"]', password);
    await this.page.click('[type="submit"]');
  }

  async getErrorMessage() {
    return this.page.locator(".error-message").innerText();
  }
}
```

```typescript
// In step definitions — use via fixture
Given("I am on the login page", async ({ loginPage }) => {
  await loginPage.goto();
});

When(
  "I log in as {string} with password {string}",
  async ({ loginPage }, username: string, password: string) => {
    await loginPage.login(username, password);
  }
);
```

---

## Review Checklist

- [ ] `defineBddConfig` paths match actual `features/` and `steps/` layout
- [ ] `bddgen` is run before `playwright test` (or combined in script)
- [ ] Step definitions use `createBdd(test)` — not raw `@cucumber/cucumber` imports
- [ ] Steps receive fixtures as first arg, Gherkin params after — not `this`
- [ ] Custom fixtures exported from `fixtures.ts` and imported in step files
- [ ] `.features-gen/` is in `.gitignore`
- [ ] `@smoke` / `@regression` tags map to `--grep` patterns in CI scripts
- [ ] `screenshot: "only-on-failure"` and `video: "retain-on-failure"` set for CI debugging
