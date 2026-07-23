# Plan — P4-001: Tutorial README

## P4-001 acceptance criteria (verbatim from TODO.md)

> Per STANDARDS.md doc voice: a reader follows the journey from empty repo
> to working package and understands each decision. Cover: why this exists
> (c3 heritage, the email-loop-moved-to-Python insight), the two halves
> (Python loop vs agent reasoning), the yoker SDK seam, the simple-email-gw
> seam, the handoff contract, the bounded tool set and the safety model,
> configuration, running it, the c3 → yoker-assistant porting map.
>
> **Persistent-session architecture:** explain the one long-lived agentic
> session — Agent constructed once at startup with a persistent context
> manager, each email delivered as the next user message, continuity living
> in the session plus memory files and `PERSONAL.md`.
>
> **Custom md→html tool story:** explain creating your own bounded tool —
> the `yoker_assistant:md_to_html` converter as a yoker plugin/tool defined
> in this package — pairing with yoker's built-in curated tools to
> demonstrate both halves of yoker's tool model. HTML replies (not plain
> text) because markdown and email do not render well together.
>
> **Dual-mode architecture:** cover the three-layer tool model — the
> package is simultaneously a consumer of yoker's built-in curated tools,
> a provider of its own named safe tool (`yoker_assistant:md_to_html`),
> and a reusable plugin any external yoker consumer can load. Explain the
> self-trust requirement for unattended operation (no TTY to prompt —
> the trust gate rejects untrusted plugins in non-interactive mode) and
> that self-consumption and third-party consumption use the identical
> mechanism (`pip install yoker-assistant` + `[plugins]` /
> `[plugins.trusted]` in `yoker.toml`).
>
> **Git commit/push demo beat:** document the visible "acts on behalf of
> the owner" moment — the agent learns a behaviour, writes `PERSONAL.md`,
> commits, and pushes via full `yoker:git` (bounded tools, not a shell).
>
> **Recipient safety:** document that it is a `simple-email-gw` config
> option (`EMAIL_RECIPIENT_WHITELIST_ADDRESSES`), not package code.
>
> **Security configuration subsection (security-engineer recommendation):**
> include a short "Security configuration" section covering: (a) the
> self-trust blast radius — marking `[plugins.trusted] yoker_assistant =
> true; pkgq = true` admits ALL tool code from those packages as trusted
> with no per-call gate, so users must pin the installed version
> (`uv pip install yoker-assistant==<version>`) and verify the source;
> (b) the correct env var name
> `EMAIL_RECIPIENT_WHITELIST_ADDRESSES` as the primary reply-safety
> boundary — it must be set to the single owner address or the agent
> could reply to arbitrary senders; the whitelist is silently disabled
> if unset/wrong (reply-to-arbitrary-senders risk); (c) the rule that
> `~/.yoker.toml` and `.env` are NEVER committed (`.env` is already
> gitignored; a user who snapshots `~/.yoker.toml` into a repo must
> gitignore it too).
>
> Use `c3:readme` for structure and badges.
>
> **Acceptance:** README tells the build story end-to-end; a new reader can
> set it up and run `python -m yoker_assistant --once`; the porting map is
> explicit about kept/removed/reworked; the persistent-session
> architecture, the custom-tool story, and the git demo beat are each
> explained as build decisions.

## Decision: expand the existing README.md

**New file vs. expand existing README.md → expand existing.**

Reasons:
- The acceptance criteria say "Write the tutorial README" (singular) and
  "the README links to it from the Security configuration subsection"
  (already done in Bucket A — `README.md` references `SECURITY.md`).
- `analysis/functional.md` §5.2 already promises "A full tutorial is in
  P4-001" and points readers at the README. Adding a second top-level doc
  splits the story across files and violates the Simplicity Principle.
- The current README is intentionally thin (~96 lines, "Skeleton" status).
  P4-001 is the task that graduates it to the full tutorial. Keeping a
  separate lean README AND a TUTORIAL.md would create two entry points
  competing for the same reader — exactly the indirection the Simplicity
  Principle rejects.
- `c3:readme` (the mandated structure skill) treats README.md as the
  primary project README; introducing a separate TUTORIAL.md would be a
  second convention not sanctioned by the skill.

**Consequence:** the existing sections (Quick start, Configuration,
Security configuration, License) are preserved and folded into the
tutorial's narrative order. The "Skeleton" Status line is updated to
reflect that the build is implemented (P1–P3 done).

## What NOT to duplicate

The README is the *story*. The analysis document is the *spec*. Cross-
reference, do not copy:

- `analysis/functional.md` §2 (full architecture) → README tells the
  narrative version; links to §2 for the full seam-by-seam spec.
- `analysis/functional.md` §3 (full porting map) → README shows the
  condensed table (kept/removed/reworked/dropped/added verdicts only);
  links to §3 for the per-element rationale.
- `analysis/functional.md` §4 (handoff contract) → README shows the
  payload format snippet and the four-way branch one-liner; links to §4
  for the full ordering/idempotency discussion.
- `SECURITY.md` (manifest review process) → README's Security
  configuration subsection links to it (already done in Bucket A).
- `analysis/functional.md` §7 (loop behavior) → README shows the per-
  iteration bullet list; links to §7 for the full error-handling table.

The README does NOT re-explain: context-window management (out of scope
by design — §8 Q11), attachment handling (out of scope), batch
processing, multi-account support — these are listed under "Out of
scope (first pass)" with a one-line pointer to TODO.md "Unsorted".

## Proposed structure (section outline)

Target length: 450–600 lines (tight tutorial, not a tome). Code
snippets are short (5–15 lines each) and point at the real source files
for the full version.

```
# yoker-assistant

<one-line tagline — kept from current README>
<two-sentence "what is this" — yoker-as-SDK showcase, dual-mode plugin>

## Status

<updated from "Skeleton" to "First pass implemented (P1–P3).">
<one line pointing at TODO.md for the remaining backlog.>

## Why this exists

<c3 heritage in three paragraphs: the c3 assistant runs inside Claude
 Code and polls email via an MCP server. The insight: the email loop is
 cheap structured work that should live in Python, not in the agent.
 The port moves the loop out and leaves the agent to do what it is good
 at — reasoning. Link to functional.md §1 for the full project overview.>

## The two halves

<the central design idea: Python owns the structured loop (poll, fetch,
 reply, archive), the agent owns the reasoning (categorize, act,
 compose). No agent cost on polling; no Python cost on reasoning. The
 seam between them is the loop module itself — there is no Mailbox
 wrapper class (descoped per owner feedback in P1-003). A simple
 ASCII diagram showing the loop and the agent split, with the handoff
 arrow between them.>

## The seams

### The yoker SDK seam

<5-line code snippet from loop.py showing `Session(config,
 session_id=...)` and `agent.process(message)`. One paragraph: yoker
 is a library-first, async, event-driven agent harness. The Agent is
 resolved by name (`yoker_assistant:assistant`) from the Session's
 plugin-loaded registry — no manual loader, no file path that breaks
 on install. Link to functional.md §2.3 for the full SDK surface.>

### The simple-email-gw seam

<5-line code snippet from loop.py showing `get_pool()` +
 `imap.connect()` + `imap.search("INBOX", "UNSEEN")`. One paragraph:
 the loop calls `IMAPClient`/`SMTPClient` directly (no wrapper), with
 `connect()`/`disconnect()` bookending each iteration — an idle
 connection across the multi-minute poll interval would just time
 out. Link to functional.md §2.4 for the connection-lifetime
 rationale.>

## The handoff contract

<the payload format — From/Subject/Date + body, no instructions block,
 shown as a fenced text block. The four-way branch on the agent's
 reply, as a 4-bullet list: {{NO_REPLY}} / empty / unsafe HTML / valid
 HTML — with one line each on what the loop does. Note that every
 send is a reply (always `reply_email`, no `send_email` fallback).
 Link to functional.md §4 for the full ordering/idempotency
 discussion.>

## The bounded tool set

<the curated tool list from assistant.md `tools:` frontmatter as a
 short table: tool | purpose. One paragraph on the safety model:
 named, guardrailed tools, no open shell — this is what the showcase
 demonstrates (Bash removed, AskUserQuestion/PushNotification/MCP
 removed). Link to functional.md §3.3 for the per-tool porting
 rationale.>

## The c3 → yoker-assistant porting map

<condensed table — five rows: KEPT / REMOVED / REWORKED / DROPPED /
 ADDED — with one-line summary and a few example elements each. Link
 to functional.md §3 for the full per-element map. State the
 adaptation principle in one sentence: keep the concepts, rework the
 mechanics.>

## The persistent-session architecture

<the one long-lived agentic session: Agent constructed ONCE at
 startup with a persistent context manager; one-time Initialize turn
 (agent reads PERSONAL.md via `yoker:read`); each email is the next
 user message in that SAME session; continuity lives in the session
 plus memory files plus PERSONAL.md learned behaviours the agent
 writes. 3–4 paragraphs. Link to functional.md §2.1 and §8 Q3 for
 the resolved design questions.>

## The custom md→html tool story

<the showcase's "create your own bounded tool" example: a plain
 Python function in `src/yoker_assistant/tools.py`, annotated with
 yoker guardrail markers, exposed via `__YOKER_MANIFEST__` in
 `__init__.py`. 5-line code snippet of the manifest. One paragraph on
 why HTML (markdown and email do not render well together). One
 paragraph on why this is the second half of yoker's tool model —
 using built-ins AND authoring your own. Link to functional.md
 §2.3.1 and §3.3.>

## Dual-mode architecture

<the three-layer tool model in one paragraph + one short bullet list:
 (1) consumer of yoker's built-in curated tools, (2) provider of its
 own named safe tool `yoker_assistant:md_to_html`, (3) reusable
 plugin any external yoker consumer can load. The self-trust
 requirement: with no TTY to prompt, yoker's trust gate rejects
 untrusted plugins in non-interactive mode — `[plugins.trusted]
 yoker_assistant = true` is required. Self-consumption and
 third-party consumption use the identical mechanism
 (`pip install yoker-assistant` + the same two `[plugins]` /
 `[plugins.trusted]` lines). Link to functional.md §2.3.1 and §8.1.>

## The git commit/push demo beat

<the visible "acts on behalf of the owner" moment, as a narrative
 paragraph: the agent learns a behaviour from an email → writes it to
 PERSONAL.md via `yoker:update` → commits and pushes via `yoker:git`
 (full git, not a shell). This is the showcase's headline
 demonstration of bounded tools acting on the owner's behalf: the
 assistant autonomously maintains its own learned-behaviours file in
 version control. Note that the loop logs the user turn and the
 agent turn with `===` separators so the demo is visible at INFO
 level. Link to functional.md §4.3.>

## Recipient safety

<one short paragraph: reply safety is a `simple-email-gw` config
 option (`EMAIL_RECIPIENT_WHITELIST_ADDRESSES`), not package code.
 The loop refuses to start if the whitelist is disabled (C1 blocking
 fix — fails open otherwise). Set the whitelist to the single owner
 address; leaving it broad lets the agent reply to arbitrary
 senders. The whitelist is silently disabled if unset/wrong. Link
 to functional.md §5.3 and §7.>

## Quick start

<kept from current README: `make env-dev`, `make test`,
 `python -m yoker_assistant --once`. Add one line: `--once` processes
 one iteration and exits (useful for demos/tests). Add a one-line
 note on backend prerequisite: yoker needs a configured backend in
 `~/.yoker.toml` (Ollama local, or a cloud API key) — this is a
 deployment prerequisite, not a code concern.>

## Configuration

<kept from current README — the two subsections `~/.yoker.toml` and
 `.env` are preserved as-is. They already cover the plugin
 registration, self-trust, and the recipient whitelist. Add a one-
 line cross-reference to the Security configuration subsection below
 for the blast-radius discussion, and to `yoker.toml.example` /
 `.env.example` for the reference templates.>

## Security configuration

<kept from current README (Bucket A) — already covers (a) the
 self-trust blast radius with version-pinning advice, (b) the
 `EMAIL_RECIPIENT_WHITELIST_ADDRESSES` env var as the primary reply-
 safety boundary, (c) the `make pre-publish` guard. Add one bullet:
 `~/.yoker.toml` and `.env` are NEVER committed (`.env` is already
 gitignored; a user who snapshots `~/.yoker.toml` into a repo must
 gitignore it too). This satisfies the third requirement of the
 security-engineer recommendation. Link to `SECURITY.md` for the
 manifest-addition review process (already linked).>

## Running it

<one short section: `python -m yoker_assistant` (long-running) vs
 `python -m yoker_assistant --once` (one iteration). SIGINT/SIGTERM
 graceful shutdown. The loop logs the user turn and the agent turn
 at INFO level so you can watch it work. One paragraph on what to
 expect the first time (the bootstrap flow when PERSONAL.md is
 missing — the agent asks the owner questions to construct it).>

## Out of scope (first pass)

<short bullet list with one-line pointers to TODO.md "Unsorted":
 HTML styling polish, attachment handling, batch processing,
 multi-account support, `make run-demo` target. One sentence each,
 no detail.>

## License

<kept: MIT.>
```

## Diagrams and code snippets

**Diagrams** (one, ASCII, ~10 lines):
- The two-halves split: Python loop on the left, agent on the right,
  handoff arrow between them. Shows poll/fetch/reply/archive on the
  Python side and categorize/act/compose on the agent side. The seam
  is the handoff arrow. No mermaid, no images — ASCII keeps the README
  portable and avoids the relative-image-path pre-publish guard.

**Code snippets** (short, illustrative, pointing at real source):
1. `__init__.py` manifest (3 lines) — for the custom-tool story.
2. `loop.py` `Session` construction (3 lines) — for the yoker SDK seam.
3. `loop.py` `get_pool` + `imap.connect` (3 lines) — for the simple-
   email-gw seam.
4. The handoff payload format (4 lines, fenced text) — for the handoff
   contract.
5. The `tools:` frontmatter from `assistant.md` (12 lines) — for the
   bounded tool set.
6. The `~/.yoker.toml` plugin block (already in README, kept).

No snippet is longer than ~12 lines. Each links to the source file for
the full version.

## Cross-references (link inventory)

From the README to:
- `analysis/functional.md` §1 (project overview) — from "Why this exists"
- `analysis/functional.md` §2.1 (loop) — from "Persistent-session
  architecture"
- `analysis/functional.md` §2.3 (yoker SDK seam) — from "The yoker SDK
  seam"
- `analysis/functional.md` §2.3.1 (dual-mode) — from "Dual-mode
  architecture" and "The custom md→html tool story"
- `analysis/functional.md` §2.4 (simple-email-gw seam) — from "The
  simple-email-gw seam"
- `analysis/functional.md` §3 (porting map) — from "The c3 →
  yoker-assistant porting map"
- `analysis/functional.md` §3.3 (bounded tool set) — from "The bounded
  tool set"
- `analysis/functional.md` §4 (handoff contract) — from "The handoff
  contract"
- `analysis/functional.md` §4.3 (demo beat) — from "The git commit/push
  demo beat"
- `analysis/functional.md` §5.3 (recipient safety) — from "Recipient
  safety"
- `analysis/functional.md` §7 (loop behavior) — from "Running it"
- `analysis/functional.md` §8 Q3 (persistent session resolution) — from
  "The persistent-session architecture"
- `analysis/functional.md` §8.1 (dual-mode summary) — from "Dual-mode
  architecture"
- `SECURITY.md` — from "Security configuration" (already linked)
- `TODO.md` — from "Status" and "Out of scope"
- `yoker.toml.example`, `.env.example` — from "Configuration"
- `src/yoker_assistant/__init__.py`, `loop.py`, `tools.py`,
  `agents/assistant.md` — from the relevant code snippets

## Acceptance criteria coverage map

| Acceptance criterion | README section |
|---|---|
| Why this exists (c3 heritage, email-loop insight) | "Why this exists" |
| The two halves (Python loop vs agent reasoning) | "The two halves" |
| The yoker SDK seam | "The seams → The yoker SDK seam" |
| The simple-email-gw seam | "The seams → The simple-email-gw seam" |
| The handoff contract | "The handoff contract" |
| The bounded tool set and the safety model | "The bounded tool set" |
| Configuration | "Configuration" (existing) |
| Running it | "Quick start" + "Running it" |
| The c3 → yoker-assistant porting map | "The c3 → yoker-assistant porting map" |
| Persistent-session architecture | "The persistent-session architecture" |
| Custom md→html tool story | "The custom md→html tool story" |
| Dual-mode architecture | "Dual-mode architecture" |
| Git commit/push demo beat | "The git commit/push demo beat" |
| Recipient safety | "Recipient safety" |
| Security configuration (a) blast radius + version pinning | "Security configuration" (existing) |
| Security configuration (b) EMAIL_RECIPIENT_WHITELIST_ADDRESSES | "Security configuration" + "Recipient safety" |
| Security configuration (c) ~/.yoker.toml/.env never committed | "Security configuration" (new bullet) |
| Use `c3:readme` for structure and badges | Applied at implementation time |
| New reader can set it up and run `python -m yoker_assistant --once` | "Quick start" + "Running it" + "Configuration" |
| Porting map explicit about kept/removed/reworked | "The c3 → yoker-assistant porting map" (condensed verdict table) |
| Persistent-session, custom-tool, git-demo each explained as build decisions | Each has its own section framed as a decision |

## Length estimate

- Existing README to keep: ~60 lines (Quick start, Configuration,
  Security configuration, License) — folded into the new order.
- New narrative sections: ~350–450 lines.
- Code snippets + tables + the ASCII diagram: ~80–100 lines.
- **Total target: 450–600 lines.** Hard cap at 700 — if it grows past
  that, the section is duplicating `functional.md` and should be
  trimmed with a cross-reference.

## Implementation notes (for the implementer, not part of the README)

1. **Use `c3:readme` skill** when writing the actual README — it
   provides the structure template and badge conventions. The plan
   above is the content outline; the skill supplies the scaffolding
   (badges, section ordering conventions, link style).
2. **Two-space indentation** per the global instruction (the existing
   README already uses this for the `~/.yoker.toml` block).
3. **No emojis** per the global instruction. The existing README has
   none; keep it that way.
4. **ASCII diagram only** — no images, no mermaid. Avoids the relative
   image path pre-publish guard in `Makefile` and keeps the README
   portable on PyPI.
5. **Preserve existing anchors** — the Security configuration
   subsection and the Configuration subsection are already linked from
   elsewhere (functional.md, SECURITY.md). Keep their headings.
6. **Do NOT touch** `analysis/functional.md` or `SECURITY.md` in this
   task — the README cross-references them as-is.
7. **Status line update** — change "Skeleton (P1-001)" to "First pass
   implemented (P1–P3). See `TODO.md` for the remaining backlog." This
   is the only edit to the existing Status section.
8. **Recipients of review:** the README is reviewed under
   `c3:project-review` (functional → domain → quality → documentation
   → completeness) before the PR is pushed, per the standard project
   workflow.

## Out of scope for this plan

- Writing the README itself (this plan is the deliverable for this
  step; implementation is a separate step).
- Editing `analysis/functional.md` (already up to date per P1-003
  errata).
- Editing `SECURITY.md` (already complete per S-01).
- Any code changes (P4-001 is docs-only).
- The `make run-demo` target (TODO.md "Unsorted" — nice to have, not
  P4-001).