# Consensus Summary — Task P1-002 (Add Runtime Dependencies)

- **Task:** P1-002 Add runtime dependencies
- **Scope:** backend (dependency wiring + config documentation)
- **Date:** 2026-07-20
- **Review source:** `analysis/security-p1-002.md`

## Invoked Agents

- **security-engineer** — invoked; produced `analysis/security-p1-002.md`.
- **api-architect** — skipped (no new API surface in P1-002; backend
  dependency wiring and config documentation only). No disagreements
  between the invoked agents (single-domain review).

## Key Decisions Agreed

1. **Local-path dev wiring mechanism.** Use `[tool.uv.sources]` for
   local-path dev wiring (`../yoker`, `../simple-email-gw`, editable) so
   it is **structurally excluded** from PyPI sdist/wheel metadata. Never
   add `file://`/`path =` entries to `[project.dependencies]` — those
   would leak into published metadata and corrupt downstream
   installability. The structural exclusion is the safety property, not
   contributor discipline.

2. **`yoker.toml.example` is reference-only.** Ships with a prominent
   REFERENCE ONLY banner explaining it documents the lines to add to
   `~/.yoker.toml` and warning that copying it to `./yoker.toml` will
   clobber the user's backend config. No real `api_key`; redact or omit
   secret-bearing fields with a comment. Reuse the structure of the
   previously-removed `yoker.toml` (local Ollama, no key) as the content
   baseline, not the filename.

3. **`.env.example` stays placeholder-only.** Existing file is correct;
   no blocking changes. `.env` stays gitignored. Minor optional
   hardening (`changeme` → `your-app-password-here`, stronger
   recipient-whitelist comment) is non-blocking and may be picked up
   during implementation.

4. **Self-trust model is the intended yoker pattern.** `[plugins.trusted]
   yoker_assistant = true; pkgq = true` is REQUIRED for unattended
   operation (no TTY → trust gate rejects untrusted plugins in
   non-interactive mode). No mechanism change. The blast radius (all
   tool code from a trusted package runs with no per-call gate) and the
   version-pinning mitigation are documented in the README (P4-001
   Security configuration subsection) and in the `yoker.toml.example`
   header.

5. **Reply safety boundary stays in `simple-email-gw`.**
   `EMAIL_RECIPIENT_ADDRESSES` is the primary reply-safety boundary and
   lives in the gateway config, not in package code. The README makes
   this operationally explicit (P4-001 Security configuration
   subsection).

## Blocking Items to Verify at Implementation

- **No path-dep leakage to built metadata.** Verify after `make build`:
  `twine check dist/*` passes AND grep of the built `METADATA` file for
  `file:` / `@ file://` returns nothing. `[project.dependencies]` must
  contain PyPI names only.
- **`yoker.toml.example` REFERENCE ONLY banner.** File opens with the
  reference-only header (see `analysis/security-p1-002.md` §4 remediation
  text) and contains no real `api_key`.

## New Backlog Items Recorded

- **S-01** (P3 — Security): `SECURITY.md` describing the review process
  for `__YOKER_MANIFEST__` additions. Land before Phase B so the review
  process exists before any second tool is added to the manifest.
- **S-02** (P3 — Security): `make pre-publish` guard rejecting
  non-registry source URLs (`file://`, `path =`) in built sdist/wheel
  metadata. Defense in depth against the path-dep leakage class.

Both recorded in `TODO.md` under a new "P3 — Security (defense in depth)"
section, ordered before P4.

## TODO.md Updates Applied

- **P1-002 scope note:** specifies `[tool.uv.sources]` as the intended
  local-path dev-wiring mechanism (structural exclusion from PyPI
  metadata, not contributor discipline).
- **P1-002 acceptance criteria:** adds the explicit "no `file://`/path
  deps leak into built sdist/wheel metadata" check via `make pre-publish`
  (or equivalent) and the `yoker.toml.example` REFERENCE ONLY header
  requirement.
- **P4-001 scope:** adds a "Security configuration" subsection covering
  self-trust blast radius + version pinning, `EMAIL_RECIPIENT_ADDRESSES`
  as the reply safety boundary, and the rule that `~/.yoker.toml` and
  `.env` are never committed.
- **New P3 — Security section:** S-01 and S-02 added with clear IDs,
  acceptance criteria, and priority rationale.

## Consensus

All invoked agents (security-engineer) approve proceeding to
implementation of P1-002. The api-architect was not invoked (no new API
surface) and raised no objections. No disagreements between invoked
agents. The blocking items are mitigable in-task via the agreed
mechanisms above; the residual risks (self-trust blast radius, supply-
chain substitution of sibling repos) are documented via the README
Security configuration subsection (P4-001) and the new S-01/S-02
backlog items, none of which block P1-002 implementation.