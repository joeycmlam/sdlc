---
id: bdd-cucumber-node
name: bdd-cucumber-node
description: 'BDD test scenarios with @cucumber/cucumber for Node.js. Use when: writing Cucumber feature files for JavaScript or TypeScript projects, implementing Given/When/Then step definitions, configuring cucumber.json or cucumber.js, setting up World objects, writing Data Tables or Doc Strings, tagging scenarios for selective runs, or debugging step definition matching in Node.js Cucumber.'
argument-hint: 'Feature name or user story to implement with Cucumber.js'
---

# BDD with @cucumber/cucumber (Node.js)

## When to Use
- Writing `.feature` files for a Node.js / TypeScript project
- Implementing step definitions in JavaScript or TypeScript
- Configuring the Cucumber runner (`cucumber.js` or `package.json`)
- Setting up a shared `World` object for state between steps

## Prerequisites

```bash
npm install --save-dev @cucumber/cucumber
# TypeScript projects also need:
npm install --save-dev ts-node @types/node
```

---

## Project Layout

```
features/
├── login.feature                   # Gherkin feature files
└── step_definitions/
    ├── login.steps.ts              # Step definitions
    └── world.ts                    # Custom World class
cucumber.js                         # Runner configuration
tsconfig.json                       # (TypeScript only)
```

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
    Given the application is running

  Scenario: Successful login with valid credentials
    When the user logs in with username "alice@example.com" and password "secret"
    Then the response status is 200
    And the response body contains "welcome"

  Scenario: Login fails with incorrect password
    When the user logs in with username "alice@example.com" and password "wrong"
    Then the response status is 401
    And the response body contains "Invalid credentials"

  Scenario Outline: Login fails with invalid email format
    When the user submits email "<email>"
    Then a validation error "<error>" is returned

    Examples:
      | email        | error                      |
      | notanemail   | Please enter a valid email |
      | @missing.com | Please enter a valid email |
```

---

### Step 2 — Create a Custom World

`features/step_definitions/world.ts` holds state shared across steps in a scenario:

```typescript
import { setWorldConstructor, World, IWorldOptions } from "@cucumber/cucumber";
import axios, { AxiosResponse } from "axios";

export interface AppWorld extends World {
  baseUrl: string;
  lastResponse: AxiosResponse | null;
}

class CustomWorld extends World implements AppWorld {
  baseUrl = process.env.BASE_URL ?? "http://localhost:3000";
  lastResponse: AxiosResponse | null = null;

  constructor(options: IWorldOptions) {
    super(options);
  }
}

setWorldConstructor(CustomWorld);
```

---

### Step 3 — Write Step Definitions

`features/step_definitions/login.steps.ts`:

```typescript
import { Given, When, Then } from "@cucumber/cucumber";
import axios from "axios";
import assert from "assert";
import type { AppWorld } from "./world";

Given("the application is running", async function (this: AppWorld) {
  // Health check or no-op if server is always running in CI
  const res = await axios.get(`${this.baseUrl}/health`);
  assert.strictEqual(res.status, 200);
});

When(
  "the user logs in with username {string} and password {string}",
  async function (this: AppWorld, username: string, password: string) {
    this.lastResponse = await axios
      .post(`${this.baseUrl}/login`, { username, password })
      .catch((e) => e.response);
  }
);

Then("the response status is {int}", function (this: AppWorld, status: number) {
  assert.strictEqual(this.lastResponse?.status, status);
});

Then(
  "the response body contains {string}",
  function (this: AppWorld, text: string) {
    assert.ok(
      JSON.stringify(this.lastResponse?.data).includes(text),
      `Expected response to contain "${text}"`
    );
  }
);
```

**Built-in parameter types:**

| Type | Syntax | Matches |
|------|--------|---------|
| `{string}` | `"value"` or `'value'` | Quoted string |
| `{int}` | `42` | Integer |
| `{float}` | `3.14` | Floating point |
| `{word}` | `foo` | Single word, no spaces |
| `{}` | anything | Any text (anonymous) |

---

### Step 4 — Configure the Runner

**`cucumber.js`** (CommonJS):

```javascript
module.exports = {
  default: {
    paths: ["features/**/*.feature"],
    require: ["features/step_definitions/**/*.ts"],
    requireModule: ["ts-node/register"],
    format: ["progress-bar", "html:reports/cucumber-report.html"],
    parallel: 2,
  },
  smoke: {
    paths: ["features/**/*.feature"],
    require: ["features/step_definitions/**/*.ts"],
    requireModule: ["ts-node/register"],
    tags: "@smoke",
  },
};
```

**Or in `package.json`:**

```json
{
  "scripts": {
    "test:bdd": "cucumber-js",
    "test:smoke": "cucumber-js --profile smoke"
  },
  "cucumber": {
    "paths": ["features/**/*.feature"],
    "require": ["features/step_definitions/**/*.ts"],
    "requireModule": ["ts-node/register"]
  }
}
```

---

### Step 5 — Use Data Tables

```gherkin
Scenario: Create multiple users
  Given the following users exist:
    | name    | role  |
    | Alice   | admin |
    | Bob     | viewer|
```

```typescript
import { DataTable } from "@cucumber/cucumber";

Given("the following users exist:", function (this: AppWorld, table: DataTable) {
  const users = table.hashes(); // [{ name: "Alice", role: "admin" }, ...]
  // or table.rows() for raw rows without header
});
```

---

### Step 6 — Run Tests

```bash
# Run all features
npx cucumber-js

# Run a specific feature file
npx cucumber-js features/login.feature

# Run scenarios with a tag
npx cucumber-js --tags @smoke

# Run with a named profile
npx cucumber-js --profile smoke

# Dry run (validates step matching without executing)
npx cucumber-js --dry-run
```

---

## Review Checklist

- [ ] Step strings match exactly between feature file and step decorator (including quotes and casing)
- [ ] `this` type is annotated with the custom World interface in TypeScript
- [ ] `setWorldConstructor` is imported and called in `world.ts`
- [ ] `world.ts` is included in `require` glob pattern
- [ ] Async steps use `async function` and `await` — not arrow functions (to preserve `this`)
- [ ] Data Tables use `table.hashes()` for header rows, `table.rows()` for raw
- [ ] Tags are defined in `cucumber.js` profiles for selective CI runs
- [ ] `--dry-run` passes before running against a live environment
