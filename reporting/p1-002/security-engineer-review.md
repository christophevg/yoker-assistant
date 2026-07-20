# Security Review — P1-002 IMPLEMENTATION (Stage b)

Branch: `feature/p1-002-runtime-deps`
Reviewer: security-engineer
Date: 2026-07-20
Prior review: `analysis/security-p1-002.md` (plan-level)

## Verdict

**Approved.** Both blocking findings from the plan review are resolved in the
working-tree implementation, and all related items are satisfied. The
owner-directed PyPI-only constraint (no `[tool.uv.sources]`, no local-path
overrides) is honored. The implementation is publishable from a security
standpoint, pending the implementer committing the new files (see note below).

## Blocking Item 1 — Path-dep leakage to PyPI — RESOLVED

**Checks performed.**

1. `grep -nE "tool.uv.sources|file://|path =" pyproject.toml` → no matches.
   There is no `[tool.uv.sources]` table and no path/file URL anywhere in
   `pyproject.toml`.
2. `[project.dependencies]` contains only PyPI names with lower-bound pins:
   - `yoker>=0.8.0`
   - `simple-email-gw>=0.3.0`
   - `pkgq>=0.3.2`
   No `@ file://…`, no `path =`, no editable overrides. The published
   dependency surface is registry-only.
3. Built wheel METADATA verified directly. Extracted
   `dist/yoker_assistant-0.1.0-py3-none-any.whl` METADATA and inspected
   `Requires-Dist` lines — every entry is `name>=version` (or
   `name>=version; extra == '…'`); zero `@ <url>` forms, zero path URLs.
   `Requires-Dist` list (excerpt):
   ```
   Requires-Dist: pkgq>=0.3.2
   Requires-Dist: simple-email-gw>=0.3.0
   Requires-Dist: yoker>=0.8.0
   …dev/docs extras…
   ```
4. `uv run twine check dist/*` → PASSED for both the wheel and the sdist.
5. `uv.lock` contains `source = { editable = "." }` only for the
   `yoker-assistant` self-package (line 4427) — this is the standard
   self-install in dev mode and does **not** enter the wheel metadata. All
   third-party packages resolve to `files.pythonhosted.org` URLs (verified
   for `yoker` at line ~4420). No sibling-repo path deps anywhere in the
   lockfile.

**Approach soundness.** The developer's `make build + twine check + METADATA
grep` approach is sound:
- `make build` produces wheel + sdist via hatchling.
- `twine check` validates metadata format/syntax (catches malformed entries
  but does not reject `file://` URLs on its own — so the grep is essential).
- Grepping the built `METADATA` for `file:|@ ` closes the gap twine leaves.
  I confirmed the result independently by extracting the wheel's METADATA
  with Python's `zipfile` module: zero non-registry sources.

**Classification: Blocking → RESOLVED.**

## Blocking Item 2 — yoker.toml.example mistaken-for-active-config — RESOLVED

**Checks performed** against `yoker.toml.example` (currently untracked, in
working tree):

1. **Banner present.** Lines 1–16 open with:
   ```
   # ============================================================================
   # REFERENCE ONLY — DO NOT USE AS-IS.
   # …
   # Do NOT copy this file to ./yoker.toml. Do NOT commit a filled-in copy.
   # …
   # ============================================================================
   ```
   The banner states the clobber risk (`./yoker.toml` is read from cwd and
   WILL CLOBBER the user's backend/model config), names the correct target
   (`~/.yoker.toml`), and explicitly forbids copying to `./yoker.toml` and
   committing filled-in copies. Matches the recommended remediation text
   from the plan review verbatim in intent.
2. **No real api_key.** Line 47:
   ```
   # api_key = "REDACTED"  # set only for cloud providers, in ~/.yoker.toml
   ```
   The field is commented out with a `REDACTED` placeholder and a pointer to
   `~/.yoker.toml` as the only place to set a real key. The default shown is
   local Ollama with no key — the same safe baseline as the previously
   removed `yoker.toml`.
3. **Self-trust blast radius documented in-file.** Lines 12–15:
   > "Self-trust blast radius: marking [plugins.trusted] yoker_assistant = true
   > (and pkgq = true) admits ALL tool code from those packages as trusted with
   > no per-call gate. Pin the installed versions (`uv pip install
   > yoker-assistant==<version>`) and verify the source."

**Classification: Blocking → RESOLVED.**

## Related Items — All Satisfied

### Self-trust blast radius documented in README + yoker.toml.example
- `README.md` lines 51–56: states self-trust is required for unattended
  operation, names the blast radius ("all tool code from a trusted package
  runs with no per-call gate"), and instructs version pinning with
  `uv pip install yoker-assistant==<version>`.
- `yoker.toml.example` lines 12–15: same content, condensed.

### `.env.example` placeholder-only, with consequence comment
- All values are placeholders: `imap.example.com`, `smtp.example.com`,
  `assistant@example.com`, `your-app-password-here`, `owner@example.com`.
  No real credentials. The earlier `changeme` placeholder was replaced with
  `your-app-password-here` per the plan-review recommendation.
- Header comment (lines 1–6) states `.env` is for email-account credentials
  only and that backend API keys live in `~/.yoker.toml`.
- `EMAIL_RECIPIENT_ADDRESSES` comment (lines 12–14) states the consequence:
  > "the assistant may ONLY reply to addresses in this whitelist. Set to the
  > single owner address. Leaving it broad allows the agent to reply to
  > arbitrary senders."
  This satisfies the "state the consequence" recommendation.

### `.env` gitignored
- `.gitignore` line 24: `.env` excluded. `.env.example` is tracked (currently
  modified, not untracked — correct intent).

### No secrets in git history
- Files added since `6d0b178` (the yoker.toml removal commit):
  - `analysis/security-p1-002.md` (this is the plan review; contains the
    placeholder string `sk-...` in remediation text — not a real secret)
  - `reporting/p1-002/consensus.md`
  - Untracked: `reporting/p1-002/functional-analyst-review.md`,
    `yoker.toml.example`
- Secret-pattern scan across `reporting/`, `analysis/`, `yoker.toml.example`,
  `.env.example`, `README.md` returned zero real-looking secrets (only the
  `sk-...` placeholder in the analysis file, which is remediation guidance,
  not a credential).
- The previously-committed `yoker.toml` (removed in `6d0b178`) used a local
  Ollama backend with no API key — confirmed in the plan review, no
  regression here.
- No new secret-bearing files were added.

## Positive Observations

- `[project.dependencies]` uses lower-bound pins (`>=0.8.0` etc.) rather
  than floating names — the published install is reproducible in the
  intended range, satisfying the plan-review recommendation.
- The dual-mode architecture (manifest-only `__init__.py`, tools added in
  later tasks) keeps the trusted code surface minimal at P1-002.
- `yoker.toml.example` correctly reuses the structure of the previously
  removed safe `yoker.toml` (local Ollama, no key) while adding the
  reference-only banner and the `[plugins]` / `[plugins.trusted]` /
  `[skills]` blocks the user must copy to `~/.yoker.toml`.
- README cleanly separates `.env` (email-account credentials) from
  `~/.yoker.toml` (yoker runtime + backend secrets), reducing the
  misplacement risk flagged in the plan review.
- `EMAIL_RECIPIENT_ADDRESSES` is correctly framed as a `simple-email-gw`
  config concern (the gateway enforces the reply whitelist), not
  reinvented in package code.

## Non-Blocking Notes (informational, no action required for P1-002)

1. **`yoker.toml.example` is currently untracked.** It must be `git add`-ed
   by the implementer before commit. This is a workflow note, not a
   security finding — the file content is correct.
2. **Backlog items S-01 / S-02 from the plan review remain open** (a
   `SECURITY.md` describing `__YOKER_MANIFEST__` addition review, and a
   `make pre-publish` path-dep grep guard). Both are classified **New** in
   the plan review and are not blockers for P1-002. The METADATA-grep
   approach the developer ran manually is a fine interim substitute for
   S-02 until that target lands.
3. **`uv.lock` resolves the three runtime deps from `files.pythonhosted.org`
   with hashes** — supply-chain provenance for the published install path
   is intact.

## Classification Summary

| Finding (from plan review) | Classification | Status |
|---|---|---|
| Path-dep leakage to PyPI | Blocking | RESOLVED (PyPI-only deps, METADATA verified clean) |
| `yoker.toml.example` mistaken-for-active-config | Blocking | RESOLVED (banner, no real key, copy warning) |
| Self-trust blast radius documentation | Related | Satisfied in README + yoker.toml.example |
| `.env` / `~/.yoker.toml` credential handling | Related | Satisfied (placeholder-only, consequence comment) |
| `.env` gitignored | Related | Satisfied |
| No secrets in git history | Related | Satisfied (no new secret-bearing files) |
| `SECURITY.md` for manifest review (S-01) | New | Backlog — separate task |
| `make pre-publish` path-dep guard (S-02) | New | Backlog — manual METADATA grep used now |