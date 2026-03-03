# Instructions

At the end of each request, run `ruff`, `mypy`, and `pytest` if there are code changes on backend.
At the end of each request, run `npm run verify` if there are code changes in `frontend/`.
If backend API routes/schemas change, always run `npm run generate:api` in `frontend/` and migrate frontend calls to generated client/hook/types only (no custom handwritten API wrappers).
Backend tests must run on Postgres only (no SQLite fallback). Use `./run_backend_tests_postgres.sh` to prepare/reset the test DB and execute pytest.
Use backend/.venv/bin/python3 instead of python to run python scripts manually.

No legacy code.

## Exact command usage in this environment

Use these exact working directories and commands so you do not mix repo-root and backend-root execution:

- Backend lint:
  - from `/Users/nazareka/projects/Speedrulingo/backend`
  - prefer `make lint`
- Backend typecheck:
  - from `/Users/nazareka/projects/Speedrulingo/backend`
  - prefer `make type`
- Backend tests:
  - from `/Users/nazareka/projects/Speedrulingo`
  - run `./run_backend_tests_postgres.sh`
- Manual Python scripts for backend:
  - from `/Users/nazareka/projects/Speedrulingo/backend`
  - run `backend/.venv/bin/python3 ...` only when a direct Python invocation is needed

Do not run `./run_backend_tests_postgres.sh` from `backend/`; it lives at repo root.
Do not assume there is a repo-root `pyproject.toml`; backend Python tooling is configured in `backend/pyproject.toml`.
Do not let backend `uv` commands inherit a stale repo-root `VIRTUAL_ENV`; the `make` targets already handle that correctly.
If you must run backend `uv` directly instead of `make`, use:
- `cd /Users/nazareka/projects/Speedrulingo/backend && env -u VIRTUAL_ENV uv run ruff check .`
- `cd /Users/nazareka/projects/Speedrulingo/backend && env -u VIRTUAL_ENV uv run mypy .`

# agents.md — Linting & Typing Standards (Ruff + Mypy)

This repo is intentionally strict about linting and typing so changes stay safe, predictable, and reviewable.

## Source of truth

All linting/typing configuration lives in **`pyproject.toml`**:

- Ruff: `[tool.ruff]`, `[tool.ruff.lint]`, and related subsections (e.g. `isort`, `per-file-ignores`)
- Mypy: `[tool.mypy]` and `[[tool.mypy.overrides]]`

Do **not** add separate config files (`ruff.toml`, `setup.cfg`, `mypy.ini`) unless there is a very strong reason.

---

## How to change Ruff configuration

### What to edit
- Main settings: `[tool.ruff]`
  - `line-length`
  - `target-version`
  - `fix` (whether autofix is enabled by default)
- Rule selection: `[tool.ruff.lint]`
  - `select = [...]` (enabled rule families)
  - `ignore = [...]` (disabled rules)
- Import sorting: `[tool.ruff.lint.isort]`
- Complexity guardrail: `[tool.ruff.lint.mccabe]`
- File-specific exceptions: `[tool.ruff.lint.per-file-ignores]`

### Rules for changes
- Prefer **fixing code** over ignoring rules.
- If a rule is noisy:
  1) Try rewriting code to satisfy it.
  2) If it’s truly incompatible with our patterns, ignore it **surgically** (per-file or per-line).
  3) Only then consider global `ignore`.

### How to validate changes locally
Run these from repo root:
- `ruff format .`
- `ruff check . --fix`
- `pytest`

If you change import sorting behavior, ensure a clean import diff with `ruff check . --fix`.

---

## How to change Mypy configuration

### What to edit
- Global mypy behavior: `[tool.mypy]`
  - `strict`, `python_version`, `ignore_missing_imports`, plugins, etc.
- Targeted relaxations: `[[tool.mypy.overrides]]`
  - For tests or for specific third-party packages that lack stubs.

### Rules for changes
- Keep `strict = true` unless there is a repo-wide decision to relax typing.
- Prefer **adding typing** (annotations, Protocols, TypedDicts, generics) over disabling checks.
- Use `overrides` for:
  - `tests.*` (if you want fewer typing constraints in tests)
  - specific libraries with missing stubs

### How to validate changes locally
- `mypy .`
- `pytest`

---

## Mandatory policy: every suppression must explain why

### Ruff suppressions (`noqa`)
Any `# noqa` must include:
1) the specific rule code(s), and
2) a short human explanation.

✅ Good:
```py
from x import y  # noqa: F401  # re-exported in __init__ for public API
````

✅ Good (multiple):

```py
value = risky()  # noqa: S301,B904  # legacy crypto; upstream requires it, tracked in SECURITY-12
```

❌ Bad:

```py
from x import y  # noqa
```

### Mypy suppressions (`type: ignore`)

Any `# type: ignore` must include:

1. the error code in brackets (when possible), and
2. a short explanation.

✅ Good:

```py
token = jwt.encode(payload, key)  # type: ignore[no-any-return]  # pyjwt typing is incomplete; runtime verified
```

✅ Good:

```py
engine = create_engine(url)  # type: ignore[arg-type]  # URL validated earlier; SQLAlchemy typing too narrow here
```

❌ Bad:

```py
token = jwt.encode(payload, key)  # type: ignore
```

### Extra guidance

* If you need to suppress something repeatedly, consider:

  * a small wrapper function with a typed signature,
  * adding a local Protocol/stub,
  * or adjusting config with a narrow `overrides` entry.
* Suppressions without an explanation should be treated as a failing review item.

---

## When *not* to suppress

Do not suppress to “make CI green” if the underlying issue is real:

* untyped public APIs
* `Any` leaking from libraries into our domain models
* unsafe exception handling
* naive datetimes where timezone matters

If unsure: fix the types or refactor rather than ignoring.

---

## Quick reference: preferred commands

* Format: `ruff format .`
* Lint (with autofix): `ruff check . --fix`
* Typecheck: `mypy .`
* Tests: `pytest`
* Postgres test run: `./run_backend_tests_postgres.sh`
