# Code Review — P1-002 Add runtime dependencies

**Task:** P1-002 Add runtime dependencies
**Branch:** feature/p1-002-runtime-deps
**Reviewer:** c3:code-reviewer agent
**Date:** 2026-07-20

## Summary

P1-002 is a configuration-only task: it declares the three runtime
dependencies as PyPI names in `pyproject.toml`, adds a reference-only
`yoker.toml.example`, a placeholder-only `.env.example`, a minimal
Configuration section in the README, a `.gitignore` guard for `yoker.toml`,
and refreshes `uv.lock`. No new Python code was introduced. The review
verifies that the configuration is tight (no local-path leakage into PyPI
metadata), consistent across files, and aligned with the owner directive
(PyPI packages only).

## Files Reviewed

- `pyproject.toml`
- `yoker.toml.example` (new)
- `.env.example`
- `README.md`
- `.gitignore`
- `uv.lock`

## Tight Code Assessment

The task ships no Python source, so tight-code review applies to the
configuration surfaces:

- **`pyproject.toml` `[project.dependencies]`** declares exactly three
  runtime deps — `yoker>=0.8.0`, `simple-email-gw>=0.3.0`, `pkgq>=0.3.2` —
  as PyPI names with inline rationale comments. There is no
  `[tool.uv.sources]` block, no `file://`, no `path =` entries. This is the
  safety property the security-engineer asked for, expressed structurally
  rather than by contributor discipline.
- **`yoker.toml.example`** is 16 lines of `REFERENCE ONLY` documentation,
  not active config. The banner explains the cwd-vs-home trap (yoker reads
  `./yoker.toml` and `~/.yoker.toml`, not the package install location) and
  the self-trust blast radius (`[plugins.trusted] yoker_assistant = true;
  pkgq = true` admits ALL tool code from those packages as trusted, no
  per-call gate).
- **`.env.example`** is placeholder-only. The password placeholder was
  hardened to `your-app-password-here` (no real value). The
  `EMAIL_RECIPIENT_ADDRESSES` comment states the reply-safety consequence
  (the agent replies only to addresses in this list).
- **`README.md`** Configuration section is consistent with the example
  files; it does not re-document or contradict the banner text.
- **`uv.lock`** resolves the three deps to `yoker 0.8.0`,
  `simple-email-gw 0.3.0`, and `pkgq 0.3.2`, matching the lower bounds in
  `pyproject.toml`.

## Design Assessment

The design choice — PyPI-only deps, no `[tool.uv.sources]` — is the right
one for a package that will publish to PyPI. Local-path dev wiring is a
contributor's concern, not a published-package concern; keeping it out of
the repo metadata structurally prevents the path-dep leakage class that
the security-engineer flagged as blocking. The lower bounds pin to the
SDK surface that `functional.md` §2.3/§2.4 documents (`yoker` ≥0.8.0 for
the persistent context manager + `Agent` API, `simple-email-gw` ≥0.3.0
for the async IMAP/SMTP clients, `pkgq` ≥0.3.2 for the `pkgq:find` plugin
tool).

The `yoker.toml.example`-as-reference-only pattern (not active config)
resolves the cwd-vs-home config resolution trap cleanly: the repo never
ships an active `yoker.toml` that could clobber a user's backend config,
and the banner makes the trap explicit so a contributor copying the file
to `~/.yoker.toml` knows where it belongs.

## Quality Issues

None blocking. Three polish notes (non-blocking):

- **L1 (gitignore guard):** add `yoker.toml` to `.gitignore` with a
  `!yoker.toml.example` negation so a contributor who snapshots an active
  `yoker.toml` into the repo does not commit secrets. **APPLIED** during
  this review cycle — `.gitignore` now contains the guard.
- **L2 (placeholder author email):** `pyproject.toml` lists
  `christophe.vg@example.com` as author email. Replace with the real
  address before the first PyPI publish. **Release-prep** follow-up, not
  this task.
- **L3 (app-specific-password nudge):** `.env.example` could add a
  one-line note pointing users at their provider's app-specific-password
  flow (Gmail et al. reject the account password for IMAP/SMTP auth).
  Optional; the placeholder `your-app-password-here` already hints at it.

## Test Coverage

No new Python code, so no unit tests to add. `make check` runs the
existing 1 test (smoke test from P1-001) plus format/lint/typecheck — all
green. The functional coverage for this task lives at the integration
boundary: `make env-dev` resolves all deps from PyPI, `make pre-publish`
confirms no path-dep leakage into built metadata. Both pass.

## Documentation

The README Configuration section is minimal and correct — it points at
the example files rather than duplicating their content, and it does not
contradict the `yoker.toml.example` banner. The `REFERENCE ONLY` banner
in `yoker.toml.example` and the `EMAIL_RECIPIENT_ADDRESSES` comment in
`.env.example` carry the load-bearing documentation; both are tight and
explain the consequence (self-trust blast radius; reply-safety boundary)
rather than restating the obvious.

## Maintainability

**5/5.** The configuration is small, each block has an inline rationale,
and the example files document their own traps inline. A future
contributor can read `yoker.toml.example` and `.env.example` top-to-bottom
and understand the constraints without external context. The L1 gitignore
guard closes the only real maintenance hazard (accidental secret commit).

## Verdict

**Approved.** Configuration-only task, no new Python code. The owner
directive (PyPI-only deps, no `[tool.uv.sources]`, no local-path overrides)
is honored structurally. The three non-blocking polish notes are recorded
as follow-ups; L1 was applied during this review cycle.