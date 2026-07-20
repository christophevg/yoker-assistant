# P1-002 — Add runtime dependencies (Task Summary)

- **Task:** P1-002 Add runtime dependencies
- **Branch:** `feature/p1-002-runtime-deps`
- **PR:** #2 — https://github.com/christophevg/yoker-assistant/pull/2
- **Status:** pending review (implementation complete, all review stages approved, `make check` green; awaiting owner merge)

## What was implemented

- PyPI-only runtime deps in `pyproject.toml`: `yoker>=0.8.0`, `simple-email-gw>=0.3.0`, `pkgq>=0.3.2` — declared as PyPI names with inline rationale comments.
- `yoker.toml.example` — 16-line `REFERENCE ONLY` reference config (not active config) with a banner explaining the cwd-vs-home config resolution trap and the self-trust blast radius.
- `.env.example` — placeholder-only (`your-app-password-here`) email account config; `EMAIL_RECIPIENT_ADDRESSES` comment states the reply-safety consequence.
- `README.md` — minimal Configuration section pointing at the example files.
- `.gitignore` guard for `yoker.toml` (with `!yoker.toml.example` negation so the example stays tracked).
- `uv.lock` refreshed to resolve `yoker 0.8.0`, `simple-email-gw 0.3.0`, `pkgq 0.3.2`.

## Owner directive honored

No `[tool.uv.sources]`, no local-path overrides — PyPI packages only. Local-path dev wiring is a contributor concern, not a published-package concern; keeping it out of repo metadata structurally prevents the path-dep leakage class that the security-engineer flagged as blocking.

## Key decisions

- **PyPI-only deps (owner directive)** — resolves the security-engineer's path-dep-leakage blocking concern structurally rather than by contributor discipline.
- **`yoker.toml.example` is reference-only documentation, not active config** — the repo never ships an active `yoker.toml` that could clobber a user's backend config; the banner documents the self-trust blast radius inline.
- **Reply safety boundary stays in `simple-email-gw`** via `EMAIL_RECIPIENT_ADDRESSES`, not in package code — no package-level allowlist is written.
- **Version lower bounds pin to the SDK surface** that `functional.md` §2.3/§2.4 documents: `yoker` ≥0.8.0 (persistent context manager + `Agent` API), `simple-email-gw` ≥0.3.0 (async IMAP/SMTP clients), `pkgq` ≥0.3.2 (`pkgq:find` plugin tool).

## Files modified

- `pyproject.toml`
- `yoker.toml.example` (new)
- `.env.example`
- `README.md`
- `.gitignore`
- `uv.lock`

## Review cycle

| Stage | Result |
|-------|--------|
| functional-analyst | approved |
| api-architect | approved |
| security-engineer | approved |
| code-reviewer | approved |
| testing-engineer | approved |
| end-user-documenter | approved |

`make check` passed (format, lint, typecheck, 1 test).

## Follow-ups recorded

- **pkgq tool name:** the published `pkgq` yoker plugin exposes its tool as `pkgq:find` (not `pkgq:find_package` as `functional.md` §3.2/§3.3 states). Noted in `TODO.md` P2-001 — the agent-definition `tools:` frontmatter must use `pkgq:find`. `functional.md` §3.2/§3.3 errata will be corrected when P2-001 lands.
- **S-01:** `SECURITY.md` for the `__YOKER_MANIFEST__` review process — in `TODO.md` backlog.
- **S-02:** `make pre-publish` non-registry URL guard — in `TODO.md` backlog.
- **L2:** replace placeholder author email (`christophevg@example.com`) before first PyPI publish — release-prep.
- **L3:** optional app-specific-password nudge in `.env.example`.

## Lessons learned

- The pre-existing uncommitted `Makefile` change was intentional (the project Makefile reuses the global Makefile's `help` target). It was committed separately on master as a chore, not bundled into this feature branch.
- The `c3:python-project` template may generate a redundant project-level `help` target when the project Makefile is intended to delegate to the global Makefile. Flagged for a template fix in the c3 project.
