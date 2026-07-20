# End-User Documentation Review — Task P1-002 (Add Runtime Dependencies)

- Branch: `feature/p1-002-runtime-deps`
- Reviewer: end-user-documenter
- Date: 2026-07-20
- Scope: documentation added in THIS task (README.md Configuration section,
  `yoker.toml.example`, `.env.example` changes). P4-001 owns the full
  tutorial README and is deliberately out of scope here.

## Files reviewed

- `README.md` (working-tree changes: Configuration section added, Quick
  start `make env-dev` comment updated to "(PyPI)")
- `yoker.toml.example` (new, untracked)
- `.env.example` (working-tree changes: header expanded, reply-safety
  comment strengthened, `changeme` → `your-app-password-here`)
- `TODO.md` (P1-002 acceptance criteria)
- `analysis/functional.md` §5 Configuration Model
- `reporting/p1-002/consensus.md` (owner directive: PyPI-only, no
  `[tool.uv.sources]`, no local-path dev wiring in docs)

## Acceptance criteria check

| # | Criterion (from TODO.md P1-002 + this task's brief) | Verdict | Evidence |
|---|---|---|---|
| 1 | README documents the required `~/.yoker.toml` lines (plugin registration, self-trust, `skills.directories`) | PASS | README §"~/.yoker.toml — yoker runtime" embeds a toml block with `[plugins] enabled = true; packages = ["yoker_assistant", "pkgq"]`, `[plugins.trusted] yoker_assistant = true; pkgq = true`, `[skills] directories = ["./skills"]`. All three required groups present. |
| 2 | Clear that user must add these to `~/.yoker.toml` (NOT a repo-level `yoker.toml`), and why | PASS | README explicitly: "plugin registration belongs in `~/.yoker.toml`" with the reason "A repo-level `./yoker.toml` is only read during local dev and would clobber the user's backend/model config." Matches functional.md §5.2 and the dual-mode rationale in §2.3.1. |
| 3 | Documents `.env` fields and the reply-safety boundary (`EMAIL_RECIPIENT_ADDRESSES`) | PASS | README §".env — email account" lists all five fields (`EMAIL_IMAP_HOST`, `EMAIL_SMTP_HOST`, `EMAIL_USERNAME`, `EMAIL_PASSWORD`, `EMAIL_RECIPIENT_ADDRESSES`) and a dedicated paragraph names `EMAIL_RECIPIENT_ADDRESSES` as the "**primary reply-safety boundary**" with the single-owner-address guidance and the "simple-email-gw config concern, not package code" framing. |
| 4 | Notes `~/.yoker.toml` and `.env` are never committed | PASS | README Configuration intro: "neither is committed (`.env` is gitignored; `~/.yoker.toml` lives in the user home and never enters the repo). Reference templates live in this repo." |
| 5 | README consistent with `yoker.toml.example` and `.env.example` (no contradictions, correct field names) | PASS | The embedded toml block matches `yoker.toml.example` lines 23-36 verbatim (same package list, same trust flags, same `directories = ["./skills"]`). The `.env` block matches `.env.example` field names and the `your-app-password-here` placeholder exactly. No contradictions. |
| 6 | Scope appropriate (minimal for P1-002, not duplicating P4-001's full tutorial) | PASS | README ends the `~/.yoker.toml` subsection with "A full tutorial is in P4-001." Backend/model details, security-configuration subsection, git demo beat, porting map, and persistent-session architecture are all correctly deferred to P4-001. The Configuration section is the minimum needed to make the skeleton runnable. |
| 7 | Inline doc/comment quality in `yoker.toml.example` and `.env.example` | PASS | `yoker.toml.example` opens with a 16-line REFERENCE ONLY banner explaining the clobber risk, the self-trust blast radius, and the version-pinning mitigation; section comments ("-- Plugins ...", "-- Skills ...", "-- Backend / model ...") explain WHY, not just WHAT. `.env.example` header clarifies the `.env`-vs-`~/.yoker.toml` split and the reply-safety boundary in tight prose. |

## Cross-checks

- **Owner directive (PyPI-only, no `[tool.uv.sources]`)** is reflected
  consistently: the README Quick start comment was changed from
  "(local path deps for dev)" to "(PyPI)", and no local-path dev-wiring
  instructions appear. The functional-analyst review confirms the owner
  overrode the original `[tool.uv.sources]` plan; the docs correctly do
  not promise a mechanism that was removed.
- **`yoker.toml.example` REFERENCE ONLY header** is present and prominent
  (lines 1-16), satisfying the blocking item from `consensus.md`.
- **No real `api_key`** in `yoker.toml.example` — the field is commented
  out with `# api_key = "REDACTED"  # set only for cloud providers, in
  ~/.yoker.toml`. Satisfies the "no real api_key" acceptance.
- **Self-trust blast-radius + version-pinning guidance** appears in both
  the README (lines 51-56) and the `yoker.toml.example` header (lines
  12-15) — the two are consistent and not redundant.
- **`.env` vs `~/.yoker.toml` separation of concerns** is stated in both
  files (`.env.example` header lines 5-6; README Configuration intro lines
  26-28). No bleed-through (e.g. no `EMAIL_*` key mentioned in
  `yoker.toml.example`, no `api_key` mentioned in `.env.example`).

## Polish observations (non-blocking, do not affect approval)

1. The Quick start line `python -m yoker_assistant   # entry point stub
   (exits cleanly until wired)` is accurate for the skeleton state and
   will be reworked in P4-001 — leaving it is fine.
2. The README does not state that `~/.yoker.toml` is created by yoker's
   bootstrap (functional.md §5.2 mentions this). Optional one-line
   addition for P4-001; not required by P1-002 acceptance.
3. The README does not note that `pkgq` is loaded as a yoker plugin
   (not imported directly) — this rationale lives in `pyproject.toml`
   comments. Optional to surface in P4-001; not required here.
4. README ends without a trailing newline (consistent with the P1-001
   version). Cosmetic; harmless.

## Verdict

**approved.**

The P1-002 documentation is accurate, clear, internally consistent, and
correctly scoped. All seven acceptance criteria from TODO.md and the
task brief are satisfied. The Configuration section documents the three
required `~/.yoker.toml` line groups, the `.env` fields, the reply-safety
boundary, and the never-committed rule; it correctly distinguishes
`~/.yoker.toml` from a repo-level `yoker.toml` with the clobber rationale;
and it defers the full tutorial to P4-001 without leaking P4-001 content.
The `yoker.toml.example` and `.env.example` comments are tight and
explain WHY. The polish items above are optional P4-001 refinements, not
blockers.