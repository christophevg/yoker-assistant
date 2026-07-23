# Functional Review — Stage a (BLOCKING)

**Task:** P4-001 — Tutorial README (Bucket B documentation)
**Branch:** `feature/p4-001-tutorial-readme`
**Reviewer:** functional-analyst
**Date:** 2026-07-23
**Working tree state:** docs/ folder + README.md modifications uncommitted (branch carries only `reporting/p4-001-tutorial/plan.md`); Stage a reviews the implementation in the working tree before commit.

## Verdict: **APPROVE**

All nine acceptance criteria are satisfied. `make docs` builds clean. No regressions, no broken toctree, no MyST link errors. Two minor observations below — neither is blocking.

## Per-criterion check

### 1. docs/tutorial.md tells the build story end-to-end (12 sections, narrative prose)
**PASS.** `docs/tutorial.md` (620 lines) has 12 numbered sections in narrative prose:
1. Why this exists — c3 heritage, email-loop-into-Python insight (3 paragraphs)
2. The two halves — Python loop vs agent reasoning, with ASCII diagram
3. The seams — yoker SDK seam + simple-email-gw seam, with 5-line code snippets each; "Why no wrappers" subsection
4. The handoff contract — payload format, four-way branch, ordering & idempotency
5. The bounded tool set — tool table + safety model
6. The c3 → yoker-assistant porting map — condensed verdicts (full table on porting-map.md)
7. The persistent-session architecture — build decision explained
8. The custom md→html tool story — build decision explained
9. Dual-mode architecture — three layers + self-trust requirement
10. The git commit/push demo beat — build decision explained
11. Recipient safety
12. Out of scope (first pass)

Each section is full prose, not a link list. Matches the owner's "all-inclusive, narrative on its own" directive verbatim.

### 2. A new reader can set up and run `python -m yoker_assistant --once`
**PASS.** `docs/installation.md` walks through prerequisites (Python 3.10+, uv, Ollama or cloud key, IMAP/SMTP mailbox), `make env-dev`, backend setup (`uv run yoker init`), plugin registration in `~/.yoker.toml`, `.env` from `.env.example`, and a "Verify the install" section ending with `python -m yoker_assistant --once`. `docs/quickstart.md` then walks the first run, log shape, PERSONAL.md bootstrap, and graceful shutdown. The README "Quick start" section also surfaces the same command. A new reader has a clear, linear path from clone to one-iteration run.

### 3. docs/porting-map.md is explicit about kept/removed/reworked/dropped/added
**PASS.** `docs/porting-map.md` uses all five verdicts explicitly: **KEPT**, **REMOVED**, **REWORKED**, **DROPPED**, **ADDED**, with one-line rationale per element. Three full tables (agent definition, tools list per-tool, skills per-skill) plus a high-level summary. `pa-session` is explicitly **DROPPED** with rationale (yoker context manager carries state natively). `md_to_html` is explicitly **ADDED**. Matches the acceptance criterion verbatim.

### 4. Persistent-session architecture explained as a build decision in the tutorial
**PASS.** Tutorial §7 ("The persistent-session architecture") explains: Agent constructed ONCE at startup with persistent context manager (not per email); one-time `Initialize` turn reads `PERSONAL.md`; each email is the next user message in the SAME session; continuity lives in the session + memory files + `PERSONAL.md`; context-window growth is yoker's job. The decision character is explicit — §6 ties it to "why `pa-session` was dropped", and §2 ties it to "no `Mailbox` wrapper". The section reads as a build decision, not a runtime description.

### 5. Custom md→html tool story explained as a build decision in the tutorial
**PASS.** Tutorial §8 ("The custom md→html tool story") covers: the plain Python function in `tools.py`; the 5-line `__YOKER_MANIFEST__` snippet; import-safety discipline; "Why HTML, not plain text?" (markdown and email do not render well together); "Why this is the second half of yoker's tool model" (consumer + provider). Framed as a build decision: the choice to author a custom tool, the choice of HTML as the reply format, and the choice to expose it as a plugin.

### 6. Git commit/push demo beat explained as a build decision in the tutorial
**PASS.** Tutorial §10 ("The git commit/push demo beat") narrates the four-step flow: owner emails preference → agent updates `PERSONAL.md` via `yoker:update` → agent commits + pushes via `yoker:git` (full git, not shell) → reply emails the owner. Adds the "Error surfacing in the reply" subsection — the agent reports commit/push failures in the reply rather than swallowing them. Explicitly framed as "the showcase's headline demonstration of bounded tools acting on the owner's behalf" and tied to the bounded-tool safety model (§5). The visibility-in-logs point (INFO `===` separators) is preserved.

### 7. Security configuration covers all 3 sub-points (a, b, c)
**PASS.** `docs/security.md` has dedicated sections:
- (a) "Self-trust blast radius" (lines 9-31) — admits ALL tool code, no per-call gate, `yoker:git` blast radius; mitigation bullets: pin version (`uv pip install yoker-assistant==<version>`), verify source, review `pkgq` the same way.
- (b) "Recipient whitelist — the primary reply-safety boundary" (lines 32-59) — `EMAIL_RECIPIENT_WHITELIST_ADDRESSES` (correct env var name), the wrong-name silently disables the whitelist, C1 blocking fix fails closed.
- (c) "`~/.yoker.toml` and `.env` are NEVER committed" (lines 60-72) — `.env` gitignored, `~/.yoker.toml` lives in home, user who snapshots must gitignore, `yoker.toml.example` is REFERENCE ONLY.

The README "Security configuration" section also retains all three points (Bucket A carry-over plus the new `~/.yoker.toml`/`.env` bullet), satisfying the README-side requirement.

### 8. README.md follows c3:readme standards (badges, structure)
**PASS.** README.md (164 lines, within the 120–180 target) follows `c3:readme`:
- Badges: Python, uv, CI, License, Agentic — five badges at the top, all using shields.io with reference-style link definitions at the bottom.
- Structure: tagline → status → quick start → configuration → security configuration → running it → documentation → license. Matches the c3:readme front-door pattern.
- Tagline uses a blockquote (`>`), matching the c3:readme convention.
- The "Documentation" section is the single hand-off to ReadTheDocs, with the Tutorial linked first and supporting pages listed. All links are absolute ReadTheDocs URLs (work on PyPI per owner's constraint).
- Status section updated from "Skeleton" to "First pass implemented (P1–P3)".

### 9. c3:readme skill updated with cross-link to c3:documentation
**PASS.** `/Users/xtof/Workspace/agentic/c3/skills/readme/SKILL.md` lines 22-28 now state: "The README is the front-door. Full end-user documentation lives in a `docs/` folder published to ReadTheDocs (Sphinx + MyST + `sphinx_rtd_theme`). This skill covers the README; the docs/ standard is covered by the [`c3:documentation`](../documentation/SKILL.md) skill." Lines 340 also reference `c3:documentation` as "the docs/ + Sphinx + ReadTheDocs standard. README is the front-door; `docs/` is the full narrative." This is the standards improvement the owner asked for; it is implemented.

## Owner's two follow-up directives

### "Make sure to improve C3 cross links to ensure better adoption of README <-> docs/ relation."
**PASS.** Three layers of cross-linking:
- c3:readme skill → c3:documentation skill (link above).
- README → docs/ via the "Documentation" section with absolute ReadTheDocs URLs.
- docs/ pages cross-reference the README implicitly (the tutorial closes with "supporting pages hold the long-form reference") and link to each other via MyST `{doc}` / relative refs (`[Tutorial](tutorial.md)`, `[Security](security.md)`, etc.) that resolve at Sphinx build time.

### "Also ensure to apply our standards about README files, including badges,..."
**PASS.** Covered by criterion 8 above — badges, blockquote tagline, front-door structure, status block, documentation hand-off section, license section, reference-style link definitions.

## Edge case & regression check

### README "Security configuration" section preserved from Bucket A
**PASS.** The section is present (README lines 93-110), retains the self-trust blast radius + version pinning, retains the `EMAIL_RECIPIENT_WHITELIST_ADDRESSES` boundary, retains the `make pre-publish` guard reference, and adds the new `~/.yoker.toml`/`.env` never-committed bullet. It links to both `SECURITY.md` (repo-relative, works after clone) and the ReadTheDocs Security page (absolute, works on PyPI).

### docs/ pages cross-reference SECURITY.md correctly
**PASS.** `docs/security.md` lines 5-7 explicitly state the source `SECURITY.md` documents the manifest-addition review process and this page cross-references it; the "manifest-addition review process" section (lines 73-111) paraphrases the four-step process and cites `SECURITY.md` as the authoritative text. `SECURITY.md` itself is unchanged (out of scope per the plan).

### Broken MyST links or toctree entries
**PASS.** `docs/index.md` toctree lists `installation, quickstart, tutorial, architecture, porting-map, security, configuration, api, changelog` — all nine files exist in `docs/`. MyST `{doc}`/relative references inside docs/ all resolve to existing files. No broken references reported by Sphinx.

### `make docs` builds clean
**PASS.** `make docs` output: "build succeeded." Sphinx v9.1.0, myst v5.1.0, no warnings, no errors. Autodoc directives in `docs/api.md` resolve (`yoker_assistant.loop.run`, `yoker_assistant.loop.build_message`, `yoker_assistant.tools.md_to_html` all picked up — `highlighting module code: yoker_assistant.loop, yoker_assistant.tools`).

### `.readthedocs.yaml` and `docs/requirements.txt`
**PASS.** `.readthedocs.yaml` uses the standard form (Python 3.12, Sphinx config `docs/conf.py`, pip install with `docs` extra). `docs/requirements.txt` pins `sphinx>=7.0.0`, `sphinx-rtd-theme>=2.0.0`, `myst-parser>=2.0.0`. `docs/conf.py` matches the c3:documentation standard (extensions, theme, myst extensions, intersphinx).

## Minor observations (non-blocking)

1. **Branch commit state vs working tree.** The feature branch only contains `reporting/p4-001-tutorial/plan.md` (two commits). The actual implementation (README.md modification, `docs/` folder, `.readthedocs.yaml`) is uncommitted in the working tree. This is fine for Stage a (we review the working tree), but the release-manager will need to commit the implementation before opening the PR. Flagging so the hand-off is explicit.

2. **docs/changelog.md `[0.1.0]` date.** The `[0.1.0]` section is dated `2026-07-23`. Today is 2026-07-23, so this is consistent — but the changelog says `[0.1.0]` is released, while the rest of the project's TODO.md still has P4-001 open. The release-manager should reconcile the changelog with the actual release line at release time (e.g., move the P4-001 docs block from `[Unreleased]` into a `[0.2.0]` section, or merge it into `[0.1.0]` if 0.1.0 has not shipped yet). Not a P4-001 blocker — this is the release-manager's call.

## Consolidated feedback

No changes required. The implementation satisfies every acceptance criterion, every owner directive, and the c3:readme + c3:documentation standards. `make docs` is green. Proceed to Stage b (domain reviews) and the quality/completeness gates.