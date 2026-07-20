# Functional Review — Task P1-002 (Add Runtime Dependencies)

- **Task:** P1-002 Add runtime dependencies
- **Branch:** `feature/p1-002-runtime-deps`
- **Reviewer:** functional-analyst
- **Date:** 2026-07-20
- **Review source:** working tree at `73afd81` plus uncommitted modifications to
  `pyproject.toml`, `uv.lock`, `.env.example`, `README.md`, and the new
  `yoker.toml.example`

## Summary

The implementation lands the three runtime dependencies (`yoker`, `simple-email-gw`,
`pkgq`) as PyPI names with sensible lower-bound version pins, ships a
reference-only `yoker.toml.example`, hardens `.env.example`, and updates the README
with the required `~/.yoker.toml` plugin-registration block, the self-trust
rationale, and the `EMAIL_RECIPIENT_ADDRESSES` reply-safety boundary note. The
owner directive (no local source trees / no `[tool.uv.sources]` / no path deps
in `[project.dependencies]`) is honored — the published metadata is PyPI-only,
verified by `make build` + `twine check` + a METADATA grep for `file:` / `@ file:`
(both clean). `make check` passes (format, lint, mypy, 1 test). All eight
acceptance criteria from TODO.md plus the security additions are met.

One process note (non-blocking): the implementation changes sit in the working
tree on top of the branch's last commit (`73afd81`); `git diff master..feature`
only shows the analysis/TODO/reporting docs. The developer should commit the
implementation before opening the PR — but the changes are real, on disk, and
verified by this review.

## Acceptance Criteria Checklist

| # | Criterion (from TODO.md + security additions) | Status | Evidence |
|---|---|---|---|
| 1 | `make env-dev` resolves all deps (yoker, simple-email-gw, pkgq) | PASS | `make env-dev` → `uv sync --all-extras` resolves 175 packages, checks 159. `uv.lock` resolves `yoker 0.8.0`, `simple-email-gw 0.3.0`, `pkgq 0.3.2` from `https://pypi.org/simple`. |
| 2 | README documents the required `~/.yoker.toml` lines (plugin registration, self-trust, skills dir) | PASS | README §"~/.yoker.toml — yoker runtime" includes `[plugins] enabled = true; packages = ["yoker_assistant", "pkgq"]`, `[plugins.trusted] yoker_assistant = true; pkgq = true`, `[skills] directories = ["./skills"]`, plus the self-trust rationale and pinning guidance. |
| 3 | `yoker.toml.example` provided as reference with a REFERENCE ONLY header and no real `api_key` | PASS | File opens with a 16-line REFERENCE ONLY banner explaining the cwd-vs-home trap and self-trust blast radius. Backend block uses local Ollama with `# api_key = "REDACTED"` (commented). No real key. |
| 4 | No `file://`/path deps leak into built sdist/wheel metadata | PASS | `make build` produced `dist/yoker_assistant-0.1.0.tar.gz` and `.whl`. `uv run twine check dist/*` → both PASSED. `grep -iE 'file:\|@ file:\|path = ' METADATA` → no matches. `Requires-Dist` lines are `pkgq>=0.3.2`, `simple-email-gw>=0.3.0`, `yoker>=0.8.0` (+ dev/docs extras). The approach (build + twine check + METADATA grep) is the agreed verification per consensus.md and is sound: `twine check` catches PyPI-invalid metadata; the grep catches the specific `file:`/`@ file://` leakage class the security-engineer flagged. |
| 5 | No `[tool.uv.sources]` / no path deps in `[project.dependencies]` (PyPI only, owner directive) | PASS | `grep -nE 'tool.uv.sources\|^\[tool.uv' pyproject.toml uv.lock` → no matches. `grep -nE 'file:\|file://\|path = ' pyproject.toml` → no matches. `[project.dependencies]` has only `yoker>=0.8.0`, `simple-email-gw>=0.3.0`, `pkgq>=0.3.2`. Owner directive honored exactly. |
| 6 | `.env.example` is placeholder-only; `.env` is gitignored | PASS | `.env.example` values: `imap.example.com`, `smtp.example.com`, `assistant@example.com`, `your-app-password-here`, `owner@example.com`. All placeholders. `.gitignore` line 24: `.env`. `git ls-files` confirms `.env.example` tracked, `.env` not. |
| 7 | `EMAIL_RECIPIENT_ADDRESSES` comment states it is the reply safety boundary | PASS | `.env.example` lines 12-14: "Reply safety boundary (simple-email-gw): the assistant may ONLY reply to addresses in this whitelist. Set to the single owner address. Leaving it broad allows the agent to reply to arbitrary senders." README §".env" repeats the framing: "primary reply-safety boundary". |
| 8 | README notes `~/.yoker.toml` and `.env` are never committed | PASS | README §Configuration line 26-28: "neither is committed (`.env` is gitignored; `~/.yoker.toml` lives in the user home and never enters the repo). Reference templates live in this repo." |

## Findings

### F1 — Owner directive honored exactly (positive, blocking-item resolved)

The owner's binding directive was "no local source trees / no
`[tool.uv.sources]` — PyPI packages only." The implementation removed even the
dev-only `[tool.uv.sources]` table that the security-engineer and consensus had
recommended as the *structural* safety mechanism. Instead the implementation
relies on `[project.dependencies]` being PyPI-only by construction (no path
entries anywhere), plus the S-02 publish-time guard (still a backlog item) as
defense in depth. This is a stricter stance than consensus and is consistent
with the owner directive. Verified: no `[tool.uv]` table in `pyproject.toml`,
no path/file sources in `uv.lock`, all three runtime deps sourced from
`https://pypi.org/simple`. The publish-time guard (S-02) remains the
defense-in-depth backstop; it should land before the first PyPI release but is
not blocking P1-002.

### F2 — Version pins are sensible against functional.md §2.3/§2.4

- `yoker>=0.8.0` — functional.md §2.3 states "yoker 0.8.0, released 2026-07-15:
  `Agent` + `agent_path` + `process` is sufficient. No blocker." The lower
  bound is exactly the version that introduces the SDK surface this package
  depends on. Correct.
- `simple-email-gw>=0.3.0` — functional.md §2.4 references the async
  `IMAPClient`/`SMTPClient` + `EmailAccount` env contract; 0.3.0 is the
  current published line per the security analysis. Correct.
- `pkgq>=0.3.2` — functional.md §2.3.1 names pkgq as the plugin loaded via
  `[plugins]`; security analysis confirms 0.3.2 is the published version.
  Correct.

All three lower bounds are tight enough to be reproducible and loose enough to
admit future patch releases. Good.

### F3 — `yoker.toml.example` hardening is complete

The file:
- Opens with a 16-line REFERENCE ONLY banner matching the security-engineer's
  §4 remediation text, including the cwd-vs-home clobbering trap and the
  self-trust blast-radius warning.
- Uses the local Ollama backend shape (no key) as the baseline, matching the
  previously-removed `yoker.toml` per the security recommendation.
- Reds the `api_key` field: `# api_key = "REDACTED"  # set only for cloud
  providers, in ~/.yoker.toml`.
- Carries the `[plugins]` / `[plugins.trusted]` / `[skills]` blocks verbatim,
  making it the single source of truth a user copies from.
- Is named `.example` so a casual `ls` does not confuse it with an active
  `yoker.toml`.

Edge case "cannot be mistaken for active config" is satisfied by both the
filename convention and the banner.

### F4 — `.env.example` hardening applied

- `EMAIL_PASSWORD=your-app-password-here` — hardened from `changeme` per the
  security-engineer's minor recommendation; unambiguously a placeholder and
  nudges toward app-specific passwords.
- `EMAIL_RECIPIENT_ADDRESSES` comment strengthened to state the consequence
  ("Leaving it broad allows the agent to reply to arbitrary senders"), matching
  the security-engineer's §5 recommendation.
- Header comment clarifies `.env` is for email-account credentials only and
  backend secrets live in `~/.yoker.toml`. This closes the
  `.env` vs `~/.yoker.toml` confusion risk the security-engineer raised.

### F5 — No regressions

`make check` runs the full gate:
- `uv sync --all-extras` — 175 packages resolved, 159 checked.
- `ruff format --check` — 8 files already formatted.
- `ruff check` — all checks passed.
- `mypy src` — no issues in 7 source files.
- `pytest -v` — `tests/test_import_safety.py::test_package_imports PASSED`
  (the existing P1-001 test still passes).

No regressions introduced.

### F6 — README configuration coverage is complete

README §Configuration covers:
- The two-file split (`~/.yoker.toml` + `.env`) and the "neither is committed"
  rule (criterion 8).
- The `~/.yoker.toml` plugin-registration block verbatim (criterion 2).
- The self-trust rationale ("required for unattended operation") and the
  blast-radius / version-pinning mitigation (security-engineer §1).
- The `EMAIL_RECIPIENT_ADDRESSES` reply-safety boundary framing (criterion 7).
- The cwd-vs-home config resolution trap and why plugin registration belongs
  in `~/.yoker.toml`.

The README is scoped to P1-002 (configuration + skeleton). The full tutorial
README is P4-001 and is not expected here; the current README correctly defers
it ("A full tutorial is in P4-001").

### F7 — Process note (non-blocking)

`git status` shows the implementation changes (pyproject.toml, uv.lock,
.env.example, README.md, yoker.toml.example) are uncommitted in the working
tree on the branch. `git diff master..feature/p1-002-runtime-deps --stat`
shows only TODO.md, analysis/, and reporting/. The branch's two commits on
top of master are the docs/analysis work; the implementation itself is not yet
committed. This does not affect the functional verdict — the changes are real,
on disk, and verified — but the developer must commit before opening the PR
or the PR will be empty of the actual implementation.

## Verdict

**approved**

All eight acceptance criteria from TODO.md (including the security-engineer
additions) are met. The owner's binding directive (no local source trees, no
`[tool.uv.sources]`, PyPI-only) is honored exactly. Version pins are sensible
against functional.md §2.3/§2.4. No regressions; `make check` passes. Edge
cases (yoker.toml.example mistaken for active config, .env.example with real
values) are handled. The build-metadata verification approach (`make build` +
`twine check` + METADATA grep) is the agreed method and is sound.

Non-blocking follow-up before the PR is opened: commit the implementation
changes to the branch (currently only the docs commits are on the branch;
the pyproject.toml / uv.lock / .env.example / README.md / yoker.toml.example
modifications are in the working tree).

Non-blocking backlog items deferred to their own tasks (already recorded):
- S-01: `SECURITY.md` for `__YOKER_MANIFEST__` review process.
- S-02: `make pre-publish` no-path-dep guard (defense in depth; the primary
  safety property in P1-002 is the PyPI-only `[project.dependencies]`, which
  is verified here).