# Security Analysis — Task P1-002 (Runtime Dependencies & Configuration)

Scope: security review of P1-002 as scoped in `TODO.md` and described in
`analysis/functional.md` §2.3.1 (dual-mode architecture) and §5 (Configuration
Model). The task adds runtime dependencies (`yoker`, `simple-email-gw`, `pkgq`),
documents local-path dev wiring, documents the required `~/.yoker.toml` plugin
registration (including self-trust), and ships `yoker.toml.example` and
`.env.example` as reference documentation.

This is a design/configuration review — no code is executed, no fixes are
applied. Findings are recommendations for the implementer (python-developer) and
the functional-analyst.

## Executive Summary

The P1-002 design is largely sound. The self-trust model is an unavoidable
consequence of unattended operation (no TTY for the trust prompt) and is
acceptable *if* the package and its dependencies are pinned and installed from
trusted sources. The existing `.env.example` and `.gitignore` are correct. The
main residual risks are (a) ensuring local-path dev wiring can never leak into a
PyPI release, (b) ensuring `yoker.toml.example` cannot be mistaken for an active
config, and (c) widening the trust blast radius via `[plugins.trusted]` so that
compromise of `yoker_assistant` or `pkgq` executes fully-trusted code on the
host. None of these block P1-002; all are mitigable in-task.

## Trust Boundaries (for context)

1. **PyPI / local filesystem → installed package** — dependency provenance.
2. **`~/.yoker.toml` → yoker runtime** — user-authored trust grant; the
   `[plugins.trusted]` table is the boundary that admits plugin code into the
   trusted execution surface.
3. **Email inbox → agent session** — untrusted input (sender-controlled
   headers/body) delivered to the agent. Out of scope for P1-002 but noted: the
   handoff contract (P2-006) is where input-validation concerns will live.
4. **Agent → host** — bounded tools (`yoker:read`/`write`/`update`/`git` plus
   `yoker_assistant:md_to_html` and `pkgq:find_package`). The self-trust grant
   widens this surface: a trusted plugin's tool code runs with the agent's
   privileges without a per-call gate.

## Findings

### 1. Plugin self-trust model — Medium (OWASP A06 Insecure Design / A01 Broken Access Control)

**Context.** `[plugins.trusted] yoker_assistant = true; pkgq = true` is
documented as REQUIRED for unattended operation because yoker's trust gate
rejects untrusted plugins in non-interactive mode (no TTY to prompt). The
package is both the agent consumer (it constructs `Agent`) and a trusted plugin
provider (`yoker_assistant:md_to_html`).

**Assessment.** The self-trust requirement is internally consistent and is the
documented yoker pattern for unattended consumers. It is **not** a
misconfiguration; it is a deliberate trade-off. The risks that flow from it:

- **Blast radius.** Marking `yoker_assistant = true` means any code in the
  `yoker_assistant` package runs as a trusted plugin. If the installed package
  is ever tampered with (supply-chain compromise of PyPI, a malicious local
  edit, a compromised CI publish key), the tampered code executes with full
  trust and no per-call gate. Same for `pkgq`.
- **Self-consumption coupling.** The package trusts itself *because* it consumes
  itself. This is circular but not exploitable on its own — the risk is that a
  future contributor adds a tool to `__YOKER_MANIFEST__` without review and it
  automatically runs trusted. There is no secondary review gate inside the
  package.
- **Non-interactive widening.** Unattended mode removes the human trust prompt
  entirely. Any plugin listed in `packages` that is also marked `trusted`
  bypasses the gate forever, not per-session.

**Confidence:** High that this is the intended pattern; Medium that the blast
radius is adequately understood by end users.

**Remediation / hardening (recommend, do not apply):**

- Document the blast radius explicitly in the README and in a comment block at
  the top of `yoker.toml.example`: "Self-trust admits ALL tool code from this
  package as trusted. Pin the installed version and verify the source."
- Recommend users pin `yoker-assistant` and `pkgq` to exact versions in their
  environment (`uv pip install yoker-assistant==<version>`), and that
  `yoker.toml.example` show pinned package references in a comment rather than
  implying floating installs.
- Recommend the package maintain a `SECURITY.md` describing how
  `__YOKER_MANIFEST__` additions are reviewed, since every manifest addition
  auto-trusts on user install. (New backlog item, not in P1-002 scope.)
- No code change to the trust mechanism itself — that is yoker's contract.

**Reference:** OWASP A06:2025 (Insecure Design — trust boundary without
secondary review), A01:2025 (Broken Access Control — privileged plugin
execution).

### 2. Credential handling — Low (OWASP A02 Security Misconfiguration, A05 Injection-adjacent: secret leakage)

**Current state (verified in repo):**

- `.env.example` exists with placeholder values only: `imap.example.com`,
  `smtp.example.com`, `assistant@example.com`, `changeme`,
  `owner@example.com`. **No real credentials.** Good.
- `.gitignore` contains `.env` (the real config) and explicitly tracks
  `.env.example`. Good.
- `uv.lock` and `pyproject.toml` contain no secrets.
- The previously-committed `yoker.toml` (removed in `6d0b178`) used a local
  Ollama backend with no API key and no real secrets — verified via
  `git show 6d0b178^:yoker.toml`. No leak in history.

**Residual risks:**

- **`EMAIL_RECIPIENT_ADDRESSES` in `.env.example`.** This is a placeholder
  (`owner@example.com`) and is correctly framed as a `simple-email-gw` safety
  gate. Good. Document in the README that this whitelist is the **primary
  reply-safety boundary** and must be set to the single owner address; without
  it the agent could reply to arbitrary senders. (Functional.md §5.3 already
  states this is a gateway config concern; ensure the README makes it
  operationally explicit.)
- **`.env` vs `~/.yoker.toml` confusion.** The backend API key (for a cloud
  provider) lives in `~/.yoker.toml`, not `.env`. Document that `.env` is for
  email-account credentials only and that backend secrets live in
  `~/.yoker.toml` (which must also be gitignored if the user ever copies it
  into a repo). The package itself ships no `~/.yoker.toml`, so no package-side
  leak path exists.
- **No leak path in documented config.** The `yoker.toml.example` should
  contain NO `api_key` value (use a placeholder like `api_key = "REDACTED"` or
  omit the field with a comment). The previous `yoker.toml` used a local
  Ollama backend with no key — follow that pattern in the example.

**Confidence:** High.

**Remediation:** None blocking. Recommend the README call out
`EMAIL_RECIPIENT_ADDRESSES` as the reply-safety boundary and that
`~/.yoker.toml` must never be committed if the user snapshots it anywhere.

**Reference:** OWASP A02:2025 (Security Misconfiguration), CWE-732 (Permission
on Private Resource), CWE-312 (Cleartext Storage — `.env` is cleartext by
design; acceptable for local dev, document the risk).

### 3. Local-path dev wiring — High (OWASP A03 Software Supply Chain)

**Context.** P1-002 documents local-path wiring (`../yoker`,
`../simple-email-gw`) for development, while the published package depends on
PyPI names. `pyproject.toml` currently declares:

```
dependencies = ["yoker", "simple-email-gw", "pkgq"]
```

These are PyPI names — correct for publication. The local-path wiring must be a
**dev-only** mechanism that cannot leak into a `make publish` / PyPI upload.

**Risks:**

- **Path-dep leakage to PyPI.** If local-path deps are added to the
  `[project.dependencies]` block (e.g. `yoker @ file:///../yoker`), `hatchling`
  will embed them in the published sdist/wheel metadata. PyPI would either
  reject the upload (file:// URLs are not valid on PyPI) or, worse, the
  metadata would silently break for downstream installers. This is the
  highest-severity finding because it would corrupt the package's
  installability.
- **Supply-chain substitution.** A developer with a checkout of `../yoker` or
  `../simple-email-gw` is running code from a sibling repo. If either sibling
  repo is ever cloned over / branch-switched to an untrusted revision, the
  assistant executes that code as a trusted plugin (see finding 1). Local path
  dev is convenient but removes the PyPI provenance check for those deps.
- **Silent drift.** Local path deps can diverge from the PyPI version the
  published package claims to require. A dev pass that works against
  `../yoker@main` may fail against `yoker==0.8.0` on PyPI.

**Confidence:** High that path-dep leakage is the top risk; Medium that
contributors will remember to scope path deps to dev only without a guard.

**Remediation (recommend — implementer's choice of mechanism):**

- **Keep `[project.dependencies]` as PyPI names only.** This is already the
  case; do not change it.
- **Express local-path dev wiring via a dev-only mechanism**, one of:
  - A `[tool.uv.sources]` override table (uv-native, dev-only, never
    included in wheel metadata):
    ```
    [tool.uv.sources]
    yoker = { path = "../yoker", editable = true }
    simple-email-gw = { path = "../simple-email-gw", editable = true }
    ```
    This is the cleanest option: `[tool.uv]` tables are not part of the
    wheel/sdist metadata, so they cannot leak to PyPI.
  - Or a separate `[project.optional-dependencies.dev-local]` extra that
    contributors install explicitly and that is never in the default install.
- **Add a publish guard.** `make pre-publish` should fail if any path/file
    URL appears in the resolved dependency metadata of the built sdist. A
    one-line check (e.g. `twine check dist/*` plus a grep over the built
    METADATA) is sufficient. (Recommend adding to the publish target — may be
    a Related finding rather than in P1-002 scope; see classification.)
- **Document the dev workflow** in the README: "Run `make env-dev` against
  PyPI deps by default; for local development against sibling repos, use
  `<dev-local command>`." Make the local-path mode opt-in, not default.
- **Pin published deps.** Consider version lower bounds (`yoker>=0.8.0`)
  rather than floating names, so the published package is reproducible.

**Reference:** OWASP A03:2025 (Software Supply Chain), CWE-829 (Inclusion of
Functionality from Untrusted Sphere), PEP 508 / PEP 621.

### 4. `yoker.toml.example` — reference-only hardening — Low (OWASP A06 Insecure Design)

**Context.** The example is reference documentation, not an active config. The
prior `yoker.toml` (removed in `6d0b178`) is a good baseline: local Ollama
backend, no API key, plugins + skills wired. The example must be clearly
distinguishable from an active config so a user does not copy it verbatim into
their repo root (where it would clobber their `~/.yoker.toml` backend settings
— see functional.md §5.2 and the `6d0b178` commit rationale).

**Risks:**

- **Mistaken activation.** If a user copies `yoker.toml.example` to
  `./yoker.toml` in a checkout, yoker reads it from cwd and it clobbers their
  user backend config. This already happened once (the file was removed from
  the repo for exactly this reason). The example must make this trap
  unmissable.
- **Secret placeholder leakage.** If the example includes a real-looking
  `api_key` or a real model endpoint, a user may commit it with their real
  values substituted.

**Confidence:** High.

**Remediation (recommend):**

- Add a prominent header comment to `yoker.toml.example`:
  ```
  # ============================================================================
  # REFERENCE ONLY — DO NOT USE AS-IS.
  # This file documents the lines you must add to ~/.yoker.toml (your USER
  # config). yoker resolves config from ~/.yoker.toml (user) and ./yoker.toml
  # (cwd). A repo-level ./yoker.toml is only read during local dev and WILL
  # CLOBBER your user backend/model config. Do NOT copy this file to
  # ./yoker.toml. Do NOT commit a filled-in copy.
  # ============================================================================
  ```
- Use placeholders for any secret-bearing field: `api_key = "REDACTED"` or
  omit with a comment `# api_key = "sk-..."  # set in ~/.yoker.toml`.
- Keep the local Ollama example (no key) as the default shown; show a cloud
  provider only as a commented-out alternative with `api_key` redacted.
- Include the `[plugins]` / `[plugins.trusted]` / `[skills]` blocks verbatim
  from the documented requirement so the example is the single source of
  truth a user copies from into `~/.yoker.toml`.

**Reference:** OWASP A06:2025 (Insecure Design — footgun config), CWE-1188
(Insecure Default — the example must default to safe).

### 5. `.env.example` — template hardening — Low (already in good shape)

**Current state (verified):** The existing `.env.example` is correct:

- Minimal fields: `EMAIL_IMAP_HOST`, `EMAIL_SMTP_HOST`, `EMAIL_USERNAME`,
  `EMAIL_PASSWORD`, `EMAIL_RECIPIENT_ADDRESSES`. No extra fields leaking
  internal structure.
- Placeholder values only (`imap.example.com`, `changeme`,
  `assistant@example.com`). No real credentials.
- Header comment explains it is a template and instructs copying to `.env`.
- `.gitignore` excludes `.env` and tracks `.env.example`.

**Residual risks / minor recommendations:**

- `changeme` is a common placeholder that linting tools (e.g. `gitleaks`) may
  or may not flag; consider `EMAIL_PASSWORD=your-app-password-here` to make
  the placeholder unambiguously non-secret and to nudge users toward
  app-specific passwords rather than account passwords. Minor.
- Add a one-line note that the password should be an **app-specific password**
  (not the account's primary password) where the provider supports it. Minor;
  belongs in README rather than the example.
- `EMAIL_RECIPIENT_ADDRESSES` is a safety-critical whitelist (the reply
  boundary). Add an inline comment stressing that this must be the owner's
  address only and that leaving it broad allows the agent to reply to
  arbitrary senders. The current comment says "simple-email-gw safety gate"
  — strengthen it to state the consequence.

**Confidence:** High. No blocking issues.

**Reference:** CWE-732 (Permission on Private Resource), CWE-256 (Plaintext
Storage — acknowledged; `.env` is plaintext by design for local dev).

### 6. TODO.md recommendations for the functional-analyst

I do not edit `TODO.md` directly. Recommendations to integrate via the
functional-analyst:

- **P1-002 acceptance criteria — add an explicit "no path deps in published
  metadata" check.** Suggested wording for the acceptance line:
  "Acceptance: `make env-dev` resolves all deps; the README documents the
  required `~/.yoker.toml` lines; a `yoker.toml.example` is provided as
  reference with a REFERENCE ONLY header; `make pre-publish` (or an
  equivalent check) confirms no `file://`/path deps leak into the built
  sdist/wheel metadata."
- **P1-002 scope note — clarify the dev-wiring mechanism.** Recommend
  specifying `[tool.uv.sources]` (or equivalent dev-only override) as the
  intended mechanism so that local-path wiring is structurally excluded from
  PyPI metadata, rather than relying on contributor discipline.
- **README security note (cross-references P4-001).** Ask the
  functional-analyst to ensure the tutorial README (P4-001) includes a
  short "Security configuration" subsection covering: (a) self-trust blast
  radius and version pinning, (b) `EMAIL_RECIPIENT_ADDRESSES` as the reply
  safety boundary, (c) the rule that `~/.yoker.toml` and `.env` are never
  committed.
- **New backlog item (not P1-002):** a `SECURITY.md` describing the review
  process for additions to `__YOKER_MANIFEST__`, since every manifest
  addition auto-trusts on user install. Classify as **New** — separate task.

## Security Findings Classification

| Finding | Classification | Action |
|---------|---------------|--------|
| Self-trust blast radius & non-interactive widening | Related | Document in README + `yoker.toml.example` header; pin versions. No mechanism change. |
| `.env` / `~/.yoker.toml` credential handling | Related | Strengthen `EMAIL_RECIPIENT_ADDRESSES` comment; README note on reply safety boundary. |
| Path-dep leakage to PyPI from local-path dev wiring | **Blocking** | Use `[tool.uv.sources]` (dev-only) so path deps cannot ship; keep `[project.dependencies]` as PyPI names. |
| Path-dep supply-chain substitution (sibling repos) | Related | Document opt-in dev-local mode; default to PyPI deps in `make env-dev`. |
| `yoker.toml.example` mistaken for active config | Blocking | Add REFERENCE ONLY header; redact any secret field; warn against copying to `./yoker.toml`. |
| `.env.example` minor placeholder/comment hardening | Related | Optional rewording of `changeme` and the recipient-whitelist comment. |
| `SECURITY.md` for `__YOKER_MANIFEST__` review process | New | New backlog item (separate task). |
| `make pre-publish` no-path-dep guard | New | New backlog item; nice-to-have defense in depth. |

### Blocking / Related Findings (detail)

**Blocking — path-dep leakage:** The implementer must choose a dev-only
mechanism (recommended: `[tool.uv.sources]`) and must NOT add `file://` or
`path =` entries to `[project.dependencies]`. Verify with `make build` +
`twine check dist/*` + a grep of the built `METADATA` file for `file:` /
`@ file://` before any publish.

**Blocking — `yoker.toml.example` header:** The file must open with a
REFERENCE ONLY banner (see §4 remediation text) and must not contain any
real `api_key`. The prior removed `yoker.toml` is a safe content baseline
(local Ollama, no key) — reuse its structure, not its filename.

### New Backlog Items

- **S-01:** `SECURITY.md` describing the review process for
  `__YOKER_MANIFEST__` additions — every addition auto-trusts on user
  install via `[plugins.trusted] yoker_assistant = true`. Medium priority;
  land before any second tool is added to the manifest (i.e. before Phase B).
- **S-02:** `make pre-publish` guard that fails if the built sdist/wheel
  METADATA contains `file://`, `path =`, or any non-registry source URL.
  Low effort, high defense-in-depth value. Low/medium priority.

## Positive Observations

- `.gitignore` correctly excludes `.env` and tracks `.env.example`.
- `.env.example` contains only placeholders; no real credentials in the repo.
- The previously-committed `yoker.toml` (removed in `6d0b178`) contained no
  secrets — verified via git history. The removal itself was a correct
  security-positive decision (it prevented a repo-level config from
  clobbering user backend config).
- `pyproject.toml` `[project.dependencies]` currently uses PyPI names only —
  the publishable surface is clean as long as local-path wiring is added via
  a non-metadata channel.
- The dual-mode architecture keeps `__init__.py` to manifest-only (per
  functional.md §2.3.1), avoiding circular imports and limiting the trusted
  code surface to the explicitly-declared manifest.
- The reply-safety boundary (`EMAIL_RECIPIENT_ADDRESSES`) is correctly
  placed in the gateway (`simple-email-gw`), not reinvented in package code.
- yoker (0.8.0) and pkgq (0.3.2) are resolved from PyPI in `uv.lock` —
  reproducible provenance for the published install path.

## References

- OWASP Top 10:2025 — A01 (Broken Access Control), A02 (Security
  Misconfiguration), A03 (Software Supply Chain), A06 (Insecure Design).
- CWE-732 (Permission on Private Resource), CWE-829 (Inclusion from
  Untrusted Sphere), CWE-1188 (Insecure Default), CWE-256 (Plaintext
  Storage of Password).
- STRIDE: this review primarily addresses Tampering (config integrity),
  Information Disclosure (credential leakage), and Elevation of Privilege
  (trusted-plugin execution).
- PEP 508 / PEP 621 / uv `[tool.uv.sources]` for dev-only dependency
  overrides that do not enter wheel metadata.