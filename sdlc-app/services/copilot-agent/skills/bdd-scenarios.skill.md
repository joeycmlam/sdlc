---
id: bdd-scenarios
name: bdd-scenarios
description: 'BDD test scenario authoring using Gherkin. Use when: writing feature files, creating Given/When/Then scenarios, designing acceptance tests, doing behavior-driven development, writing cucumber tests, generating test cases from user stories or requirements, creating Scenario Outlines, or reviewing BDD coverage.'
argument-hint: 'Feature name or user story to write BDD scenarios for'
---

# BDD Scenario Authoring

## When to Use
- Turning a user story or acceptance criteria into executable test scenarios
- Writing `.feature` files in Gherkin syntax
- Reviewing whether BDD scenarios cover a feature adequately
- Deciding between Scenario vs Scenario Outline vs Background

---

## Procedure

### Step 1 — Understand the Feature

Before writing a single line of Gherkin, gather context:
1. Read the user story, ticket, or requirement provided.
2. Identify the **actor** (who), the **action** (what), and the **outcome** (why).
3. Clarify any ambiguous business rules — ask if unclear.

> Three Amigos rule: A scenario should be understandable by a developer, tester, and business analyst without explanation.

---

### Step 2 — Write the Feature Header

```gherkin
Feature: <short feature name>
  As a <role>
  I want <capability>
  So that <business value>
```

Keep the "As a / I want / So that" narrative — it anchors every scenario to a business goal.

---

### Step 3 — Identify Scenario Types

For each feature, cover:

| Scenario type       | Description                                      |
|---------------------|--------------------------------------------------|
| Happy path          | The primary success flow                         |
| Alternative paths   | Valid variations of the happy path               |
| Edge cases          | Boundary values, empty inputs, max/min           |
| Negative / error    | Invalid inputs, unauthorized access, failures    |
| State transitions   | Scenarios that change system state               |

---

### Step 4 — Write Each Scenario

Use the **Given / When / Then** pattern:

```gherkin
Scenario: <descriptive title in present tense>
  Given <initial context / precondition>
  When  <action or event>
  Then  <expected outcome>
  And   <additional outcome (if needed)>
```

**Step writing rules:**
- `Given` — sets up the world state before the action (not an action itself)
- `When` — a single, specific user or system action
- `Then` — a measurable, observable outcome; avoid implementation details
- `And` / `But` — extend the preceding step type; never start a scenario with `And`
- One `When` per scenario — if you need two `When`s, split into two scenarios
- Steps should read like plain English; avoid technical jargon

---

### Step 5 — Apply Scenario Outline for Parametrized Cases

When multiple scenarios differ only by data, collapse them into a Scenario Outline:

```gherkin
Scenario Outline: <title with <placeholder>>
  Given <context with <variable>>
  When  <action with <variable>>
  Then  <outcome with <expected>>

  Examples:
    | variable | expected |
    | value1   | result1  |
    | value2   | result2  |
```

Use Scenario Outline when ≥ 3 scenarios share identical structure with different data.

---

### Step 6 — Extract Shared Setup with Background

If every scenario in a Feature shares the same `Given` steps, extract them:

```gherkin
Background:
  Given a user is logged in as "admin"
  And the system is in "active" state
```

Use `Background` sparingly — only for truly universal preconditions. If only some scenarios share setup, keep it inline.

---

### Step 7 — Tag for Organisation

Add tags to enable selective test execution:

```gherkin
@smoke @auth
Scenario: Successful login
```

Common tagging conventions:

| Tag          | Purpose                              |
|--------------|--------------------------------------|
| `@smoke`     | Critical path, run on every build    |
| `@regression`| Full regression suite                |
| `@wip`       | Work in progress, skip in CI         |
| `@negative`  | Error and failure scenarios          |
| `@slow`      | Long-running tests                   |

---

### Step 8 — Review Checklist

Before finalising, verify each scenario:

- [ ] Title clearly describes the behaviour being tested (not "test login" but "user logs in with valid credentials")
- [ ] One `When` step per scenario
- [ ] `Then` asserts an observable outcome, not an internal state
- [ ] No UI/implementation details leak into steps (avoid "click the Submit button" — prefer "submits the form")
- [ ] Scenario is independent — does not rely on state from another scenario
- [ ] All decision branches from the acceptance criteria are covered
- [ ] Data is realistic (use domain-meaningful values, not "foo" / "bar")
- [ ] Step wording is reusable across scenarios where possible

---

## Example: Complete Feature File

```gherkin
@auth
Feature: User Login
  As a registered user
  I want to log in with my credentials
  So that I can access my account

  Background:
    Given the login page is displayed

  Scenario: Successful login with valid credentials
    When the user enters username "alice@example.com" and password "secret123"
    And submits the login form
    Then the user is redirected to the dashboard
    And a welcome message "Hello, Alice" is displayed

  Scenario: Login fails with incorrect password
    When the user enters username "alice@example.com" and password "wrong"
    And submits the login form
    Then an error message "Invalid credentials" is displayed
    And the user remains on the login page

  Scenario Outline: Login fails with invalid email format
    When the user enters username "<email>" and password "secret123"
    And submits the login form
    Then a validation error "<error>" is displayed

    Examples:
      | email         | error                        |
      | notanemail    | Please enter a valid email   |
      | @missing.com  | Please enter a valid email   |
      | alice@        | Please enter a valid email   |

  @slow
  Scenario: Account is locked after 5 failed attempts
    Given the user has failed to log in 4 times
    When the user enters an incorrect password again
    Then the account is locked
    And a message "Account locked. Contact support." is displayed
```

---

## Decision Guide

| Situation | Recommendation |
|-----------|----------------|
| Same steps with different data (≥3 cases) | Use Scenario Outline + Examples |
| All scenarios share the same Given | Use Background |
| Only some scenarios share setup | Keep Given inline |
| Scenario title feels vague | Start with the role: "User logs in with..." |
| Steps feel too implementation-specific | Raise abstraction: what, not how |
| Unsure if two behaviours are the same scenario | If they have different outcomes — split them |
