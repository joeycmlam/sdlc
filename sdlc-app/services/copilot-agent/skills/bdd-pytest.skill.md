---
id: bdd-pytest
name: bdd-pytest
description: 'BDD test scenarios with pytest-bdd in Python. Use when: writing pytest-bdd feature files, creating step definitions with @given/@when/@then decorators, setting up conftest.py for BDD fixtures, configuring pytest.ini for feature paths, generating Gherkin scenarios for Python projects, or debugging pytest-bdd step mismatches.'
argument-hint: 'Feature name or user story to implement with pytest-bdd'
---

# BDD with pytest-bdd (Python)

## When to Use
- Writing `.feature` files for a Python project
- Implementing step definitions in pytest style
- Wiring Gherkin scenarios to `conftest.py` fixtures
- Configuring pytest to discover feature files

## Prerequisites

```bash
pip install pytest pytest-bdd
```

---

## Project Layout

```
tests/
├── conftest.py                  # Shared fixtures and step imports
├── features/
│   └── login.feature            # Gherkin feature files
└── step_defs/
    └── test_login_steps.py      # Step definitions (must start with test_)
```

> pytest-bdd discovers step definition files via pytest's normal collection — the file name **must** start with `test_`.

---

## Procedure

### Step 1 — Write the Feature File

Create `tests/features/<feature>.feature`:

```gherkin
Feature: User Login
  As a registered user
  I want to log in with my credentials
  So that I can access my account

  Scenario: Successful login with valid credentials
    Given the login page is displayed
    When the user submits username "alice@example.com" and password "secret"
    Then the user is redirected to the dashboard

  Scenario: Login fails with incorrect password
    Given the login page is displayed
    When the user submits username "alice@example.com" and password "wrong"
    Then an error message "Invalid credentials" is displayed
```

---

### Step 2 — Write Step Definitions

Create `tests/step_defs/test_<feature>_steps.py`:

```python
import pytest
from pytest_bdd import given, when, then, parsers, scenarios

# Bind all scenarios from the feature file to this module
scenarios("../features/login.feature")


@given("the login page is displayed")
def login_page(page):  # 'page' is a fixture from conftest.py
    page.goto("/login")


@when(parsers.parse('the user submits username "{username}" and password "{password}"'))
def submit_login(page, username, password):
    page.fill("[name=username]", username)
    page.fill("[name=password]", password)
    page.click("[type=submit]")


@then("the user is redirected to the dashboard")
def redirected_to_dashboard(page):
    assert page.url.endswith("/dashboard")


@then(parsers.parse('an error message "{message}" is displayed'))
def error_message_displayed(page, message):
    assert page.locator(".error").inner_text() == message
```

**Parser options for step parameters:**

| Parser | Usage | Example |
|--------|-------|---------|
| `parsers.parse` | `{name}` placeholder | `parsers.parse('user "{name}"')` |
| `parsers.cfparse` | `{name:Type}` with type coercion | `parsers.cfparse('age {n:d}')` |
| `parsers.re` | Full regex | `parsers.re(r'amount (\d+)')` |

---

### Step 3 — Set Up conftest.py

`conftest.py` provides shared fixtures available to all step definition files:

```python
import pytest


@pytest.fixture
def app_client():
    """Return a test client for the application."""
    from myapp import create_app
    app = create_app({"TESTING": True})
    with app.test_client() as client:
        yield client


@pytest.fixture
def authenticated_user(app_client):
    """Log in a default test user."""
    app_client.post("/login", data={"username": "alice", "password": "secret"})
    return app_client
```

---

### Step 4 — Configure pytest

In `pytest.ini` or `pyproject.toml`:

**pytest.ini:**
```ini
[pytest]
bdd_features_base_dir = tests/features
```

**pyproject.toml:**
```toml
[tool.pytest.ini_options]
bdd_features_base_dir = "tests/features"
```

With `bdd_features_base_dir` set, use relative paths in `scenarios()`:

```python
scenarios("login.feature")  # resolved from bdd_features_base_dir
```

---

### Step 5 — Use Scenario Outline (Parametrize)

```gherkin
Scenario Outline: Login fails with invalid email format
  Given the login page is displayed
  When the user submits username "<email>" and password "secret"
  Then a validation error "<error>" is displayed

  Examples:
    | email        | error                      |
    | notanemail   | Please enter a valid email |
    | @missing.com | Please enter a valid email |
```

pytest-bdd automatically parametrizes — no extra code needed in step defs.

---

### Step 6 — Run Tests

```bash
# Run all BDD tests
pytest tests/step_defs/

# Run a specific feature
pytest tests/step_defs/test_login_steps.py

# Run with verbose Gherkin output
pytest tests/step_defs/ -v

# Run scenarios matching a tag (requires pytest-mark mapping)
pytest -m smoke
```

To map Gherkin tags to pytest marks, add to `conftest.py`:

```python
# conftest.py
import pytest
from pytest_bdd import given  # noqa: F401 — ensure registration


def pytest_bdd_before_scenario(request, feature, scenario):
    for tag in scenario.tags:
        request.applymarker(pytest.mark.smoke if tag == "smoke" else pytest.mark.skipif(False, reason=""))
```

Or use `pytest_configure` to register marks in `conftest.py`:

```python
def pytest_configure(config):
    config.addinivalue_line("markers", "smoke: critical path scenarios")
    config.addinivalue_line("markers", "regression: full regression suite")
```

---

## Review Checklist

- [ ] Feature file path matches `bdd_features_base_dir` setting
- [ ] Step definition file name starts with `test_`
- [ ] `scenarios()` is called to bind scenarios to the test module
- [ ] Each step string exactly matches between feature file and step decorator
- [ ] Fixtures are in `conftest.py`, not hardcoded in step defs
- [ ] Parametrized data uses `Scenario Outline` + `Examples` table
- [ ] `parsers.parse` used for steps with variable data
