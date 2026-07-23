# Plan — P4-001: Tutorial (README front-door + docs/ full narrative)

## Owner feedback (verbatim, PR #9)

> I disagree. The tutorial aspect of this project is important. I consider a
> README file like a front-door, it sets you up with what you minimally need.
> The tutorial should be all-inclusive and not a reduced set of links. It
> should really be a narrative on its own.
>
> Why isn't our normal approach to create end-user documentation in a `docs/`
> folder, published to readthedocs, not considered?
>
> I'd consider this the place where all user documentation is created in
> full, including the tutorial. The README can then references those pages -
> which would also work from PyPi where the README is included, but references
> to files in the repo don't work.
>
> So, please consider this approach. If this wasn't clear from our standard
> project setup procedures, we need to improve this. I consider it an
> integral part of all of our projects.

## Research findings

### The c3 standard IS clear and was missed in the original plan

There is a clear, documented standard for `docs/` + ReadTheDocs across the c3
ecosystem. The original P4-001 plan did not apply it — this is the gap the
owner flagged.

**1. `c3:documentation` skill** (`/Users/xtof/Workspace/agentic/c3/skills/documentation/SKILL.md`):
- Mandates Sphinx for publication on readthedocs.org.
- Defines the docs/ structure: `docs/conf.py`, `docs/index.md`,
  `docs/installation.md`, `docs/quickstart.md`, `docs/api/`,
  `docs/development/changelog.md`, `docs/Makefile`, `docs/requirements.txt`.
- Specifies the standard `conf.py` (extensions: `myst_parser`, `autodoc`,
  `autosummary`, `napoleon`, `viewcode`, `intersphinx`; theme:
  `sphinx_rtd_theme`).
- Specifies `make docs` (using `uv run sphinx-build`) as the build command.

**2. `end-user-documenter` agent** (`/Users/xtof/Workspace/agentic/c3/agents/end-user-documenter.md`):
- Defines documentation types explicitly: README.md (concise front-door, use
  `c3:readme`), **docs/ (the Read the Docs folder — "should contain everything
  for every audience")**, DEVELOPMENT.md, PACKAGE.md, LICENSE,
  examples/README.md.
- Output structure: `.readthedocs.yaml` + `docs/{conf.py, index, api,
  examples, installation, quick-start, usage, features/, assets/}`.
- Content in Markdown with `myst_parser`.

**3. Existing projects confirm the standard** — 10 sibling projects use the
same Sphinx + `.readthedocs.yaml` + `sphinx_rtd_theme` + `myst_parser` setup:
baseweb, bpmn-tools, clevis, clitic, maaltafels, oatk, roomz, simple-email-gw,
yoker, yoker-chat. Reference implementation: `/Users/xtof/Workspace/agentic/yoker/docs/`
(sibling project — same author, same stack, same toolchain).

**4. The yoker-assistant Makefile already has the standard `docs` and
`docs-view` targets** (from `c3:python-project`):
```
docs: env-dev ## Build HTML documentation
	cd docs && uv run sphinx-build -M html . _build
docs-view: docs ## Build and open documentation in browser
	open docs/_build/html/index.html
```
So the build plumbing is already in place — only the `docs/` content and the
`.readthedocs.yaml` config are missing.

**Conclusion:** The standard exists and is well-defined. The original plan
missed it. The revised plan below applies it.

### Tool choice

**Sphinx + MyST + `sphinx_rtd_theme` + ReadTheDocs.** This is the uniform
standard across all 10 sibling projects and both c3 skills. MkDocs is not
used anywhere in the ecosystem.

## Revised plan

### A. README.md — lean front-door

Per owner: "a front-door, it sets you up with what you minimally need." Per
`c3:readme`: concise, just enough to get started, with examples and badges.
Per PyPI constraint: links must work on PyPI (where repo-relative file links
do NOT work) — so all cross-references to docs content use absolute
ReadTheDocs URLs (or the ReadTheDocs project URL once configured).

```
# yoker-assistant

<one-line tagline — kept from current README>
<two-sentence "what is this" — yoker-as-SDK showcase, dual-mode plugin>

## Status

<updated from "Skeleton" to "First pass implemented (P1–P3).">
<one line pointing at TODO.md for the remaining backlog.>

## Quick start

<kept from current README: `make env-dev`, `make test`,
 `python -m yoker_assistant --once`. One line on `--once` (demo/test). One
 line on backend prerequisite: configured `~/.yoker.toml` backend (Ollama or
 cloud API key).>

## Configuration

<condensed: the two `~/.yoker.toml` and `.env` subsections are trimmed to the
 minimum the user needs to start. Point at the Configuration page in the
 docs for the full detail and at `yoker.toml.example` / `.env.example` for
 the reference templates.>

## Security configuration

<kept from current README (Bucket A) — already covers (a) the self-trust
 blast radius with version-pinning advice, (b) `EMAIL_RECIPIENT_WHITELIST_…
 ADDRESSES` as the primary reply-safety boundary, (c) the `make pre-publish`
 guard. Add the new bullet: `~/.yoker.toml` and `.env` are NEVER committed.
 This section stays in the README because it is front-door-critical: a user
 who gets it wrong creates a reply-to-arbitrary-senders or
 trust-any-version risk on first run. Link to SECURITY.md (already linked)
 and to the Security page in the docs for the manifest review process.>

## Running it

<one short section: long-running vs `--once`, SIGINT/SIGTERM graceful
 shutdown, what to expect the first time (PERSONAL.md bootstrap).>

## Documentation

<the front-door hand-off: one paragraph pointing at the full docs on
 ReadTheDocs — the tutorial, the architecture, the porting map, the
 build-decision stories. This is the single link that carries the tutorial
 load. Uses an absolute ReadTheDocs URL so it works on PyPI.>

## License

<kept: MIT.>
```

**Target length: 120–180 lines.** The README is intentionally NOT a
narrative — it is the front-door. The narrative lives in `docs/`.

### B. docs/ folder — full all-inclusive tutorial narrative

Per owner: "all-inclusive and not a reduced set of links. It should really
be a narrative on its own." The tutorial is the centerpiece; supporting
pages hold the architecture/porting/security detail so the tutorial itself
stays readable.

**File structure** (mirrors the `end-user-documenter` + `c3:documentation`
standard, adapted to this project):

```
docs/
  conf.py              # Sphinx config (standard, see below)
  index.md             # toctree + project intro
  installation.md      # full install (deps, backend, plugin registration)
  quickstart.md        # first-run walkthrough (run --once, watch logs)
  tutorial.md          # THE narrative — full build story end-to-end
  architecture.md      # two halves, seams, handoff contract, bounded tools,
                       # persistent-session, dual-mode, custom tool
  porting-map.md       # c3 → yoker-assistant full per-element table
  security.md          # full security configuration + recipient safety
  configuration.md      # full ~/.yoker.toml + .env reference
  api.md               # public API surface (loop, tools manifest)
  changelog.md         # development/changelog.md per keep-a-changelog
  Makefile             # standard Sphinx Makefile (optional — root Makefile
                       #   already provides `make docs`)
  requirements.txt     # sphinx, myst_parser, sphinx_rtd_theme
```

**`docs/conf.py`** (standard, per `c3:documentation` skill + yoker sibling):

```python
"""Sphinx configuration for yoker-assistant documentation."""

project = "yoker-assistant"
copyright = "2026, Christophe VG"
author = "Christophe VG"

extensions = [
  "myst_parser",
  "sphinx.ext.autodoc",
  "sphinx.ext.napoleon",
  "sphinx.ext.viewcode",
  "sphinx.ext.intersphinx",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]

myst_enable_extensions = ["colon_fence", "deflist"]

intersphinx_mapping = {
  "python": ("https://docs.python.org/3", None),
}
```

### C. docs/index.md — toctree

```
# yoker-assistant

<one-paragraph project intro — same tagline as README.>

## Contents

```{toctree}
:maxdepth: 2

installation
quickstart
tutorial
architecture
porting-map
security
configuration
api
changelog
```
```

### D. docs/tutorial.md — the full narrative

This is the centerpiece. All-inclusive, full prose, not a reduced set of
links. It tells the build story end-to-end so a reader can follow the
journey from empty repo to working package and understand each decision.

Section outline (each section is full prose, not cross-references):

1. **Why this exists** — c3 heritage in full: the c3 assistant runs inside
   Claude Code and polls email via an MCP server. The insight: the email
   loop is cheap structured work that should live in Python, not in the
   agent. The port moves the loop out and leaves the agent to do what it
   is good at — reasoning. (3–4 paragraphs.)

2. **The two halves** — the central design idea: Python owns the
   structured loop (poll, fetch, reply, archive), the agent owns the
   reasoning (categorize, act, compose). No agent cost on polling; no
   Python cost on reasoning. The seam between them is the loop module
   itself — no Mailbox wrapper (descoped per owner feedback in P1-003).
   One ASCII diagram showing the loop and the agent split, with the
   handoff arrow between them.

3. **The seams**
   - **The yoker SDK seam** — 5-line code snippet from `loop.py` showing
     `Session(config, session_id=...)` and `agent.process(message)`. One
     paragraph: yoker is a library-first, async, event-driven agent
     harness. The Agent is resolved by name from the Session's plugin-loaded
     registry — no manual loader, no file path that breaks on install.
   - **The simple-email-gw seam** — 5-line snippet from `loop.py` showing
     `get_pool()` + `imap.connect()` + `imap.search("INBOX", "UNSEEN")`.
     One paragraph: the loop calls `IMAPClient`/`SMTPClient` directly (no
     wrapper), with `connect()`/`disconnect()` bookending each iteration
     — an idle connection across the multi-minute poll interval would just
     time out.

4. **The handoff contract** — the payload format (From/Subject/Date + body,
   no instructions block) as a fenced text block. The four-way branch on
   the agent's reply as a 4-bullet list: `{{NO_REPLY}}` / empty / unsafe
   HTML / valid HTML — one line each on what the loop does. Every send is
   a reply (always `reply_email`, no `send_email` fallback). Full ordering
   and idempotency discussion lives here (moved out of functional.md §4
   — the tutorial is the canonical place; functional.md keeps the spec).

5. **The bounded tool set** — the curated tool list from `assistant.md`
   `tools:` frontmatter as a short table: tool | purpose. One paragraph on
   the safety model: named, guardrailed tools, no open shell (Bash removed,
   AskUserQuestion/PushNotification/MCP removed).

6. **The c3 → yoker-assistant porting map** — the full per-element table
   here (KEPT / REMOVED / REWORKED / DROPPED / ADDED), with one-line
   rationale per element. The adaptation principle stated once: keep the
   concepts, rework the mechanics. (The condensed verdict table from the
   original plan goes in the README; the full table goes here.)

7. **The persistent-session architecture** — the one long-lived agentic
   session: Agent constructed ONCE at startup with a persistent context
   manager; one-time Initialize turn (agent reads `PERSONAL.md` via
   `yoker:read`); each email is the next user message in that SAME session;
   continuity lives in the session plus memory files plus `PERSONAL.md`
   learned behaviours the agent writes. 3–4 paragraphs.

8. **The custom md→html tool story** — the showcase's "create your own
   bounded tool" example: a plain Python function in
   `src/yoker_assistant/tools.py`, annotated with yoker guardrail markers,
   exposed via `__YOKER_MANIFEST__` in `__init__.py`. 5-line code snippet
   of the manifest. One paragraph on why HTML (markdown and email do not
   render well together). One paragraph on why this is the second half of
   yoker's tool model — using built-ins AND authoring your own.

9. **Dual-mode architecture** — the three-layer tool model in one
   paragraph + one short bullet list: (1) consumer of yoker's built-in
   curated tools, (2) provider of its own named safe tool
   `yoker_assistant:md_to_html`, (3) reusable plugin any external yoker
   consumer can load. The self-trust requirement: with no TTY to prompt,
   yoker's trust gate rejects untrusted plugins in non-interactive mode —
   `[plugins.trusted] yoker_assistant = true` is required. Self-consumption
   and third-party consumption use the identical mechanism.

10. **The git commit/push demo beat** — the visible "acts on behalf of
    the owner" moment, as a narrative paragraph: the agent learns a
    behaviour from an email → writes it to `PERSONAL.md` via
    `yoker:update` → commits and pushes via `yoker:git` (full git, not a
    shell). This is the showcase's headline demonstration of bounded tools
    acting on the owner's behalf: the assistant autonomously maintains its
    own learned-behaviours file in version control. The loop logs the
    user turn and the agent turn with `===` separators so the demo is
    visible at INFO level.

11. **Recipient safety** — one short paragraph: reply safety is a
    `simple-email-gw` config option
    (`EMAIL_RECIPIENT_WHITELIST_ADDRESSES`), not package code. The loop
    refuses to start if the whitelist is disabled (C1 blocking fix — fails
    open otherwise). Set the whitelist to the single owner address;
    leaving it broad lets the agent reply to arbitrary senders. The
    whitelist is silently disabled if unset/wrong.

12. **Out of scope (first pass)** — short bullet list with one-line
    pointers to TODO.md "Unsorted": HTML styling polish, attachment
    handling, batch processing, multi-account support, `make run-demo`
    target.

**Target length: 600–800 lines for `tutorial.md`.** No hard cap — the
tutorial is explicitly all-inclusive per the owner's directive. The
supporting pages (`architecture.md`, `porting-map.md`, `security.md`,
`configuration.md`) hold the long-form reference material so the tutorial
itself can flow as a narrative.

### E. Supporting docs pages (outline only)

- **`installation.md`** — full install: uv, `make env-dev`, backend
  prerequisite (Ollama local OR cloud API key), `~/.yoker.toml` plugin
  registration block, `[plugins.trusted]` self-trust, `.env` with
  `EMAIL_RECIPIENT_WHITELIST_ADDRESSES`. Reference templates:
  `yoker.toml.example`, `.env.example`.
- **`quickstart.md`** — first-run walkthrough: `python -m
  yoker_assistant --once`, watch the INFO logs (user turn / agent turn
  `===` separators), the PERSONAL.md bootstrap flow on first real run.
- **`architecture.md`** — the full seam-by-seam architecture (from
  functional.md §2, rewritten as user documentation, not spec). Loop
  module, yoker SDK seam, simple-email-gw seam, handoff contract,
  persistent-session, dual-mode, custom tool — each in full.
- **`porting-map.md`** — the full per-element c3 → yoker-assistant table
  (from functional.md §3) with kept/removed/reworked/dropped/added
  verdicts and rationale.
- **`security.md`** — full security configuration: (a) self-trust blast
  radius + version pinning, (b) `EMAIL_RECIPIENT_WHITELIST_ADDRESSES` as
  reply-safety boundary, (c) `~/.yoker.toml` / `.env` never committed, (d)
  the manifest-addition review process from `SECURITY.md` (linked or
  transcluded).
- **`configuration.md`** — full `~/.yoker.toml` and `.env` reference.
- **`api.md`** — public API surface: the loop entrypoint, the tools
  manifest (`__YOKER_MANIFEST__`), the `python -m yoker_assistant` CLI.
  Uses autodoc directives where the source has docstrings.
- **`changelog.md`** — Keep a Changelog format, seeded with the P1–P4
  history (this can start minimal and grow; the release-manager owns it
  going forward).

### F. ReadTheDocs setup

**`.readthedocs.yaml`** (standard, per sibling projects):

```yaml
# ReadTheDocs configuration

version: 2

build:
  os: ubuntu-22.04
  tools:
    python: "3.12"

sphinx:
  configuration: docs/conf.py

python:
  install:
    - method: pip
      path: .
      extra_requirements:
        - docs
```

**`docs/requirements.txt`** (or a `docs` extra in `pyproject.toml`):
```
sphinx
myst_parser
sphinx_rtd_theme
```

**`docs/Makefile`** (optional — the root Makefile's `docs` target already
runs `cd docs && uv run sphinx-build -M html . _build`, so a `docs/Makefile`
is redundant; include only if `c3:documentation` skill strictly requires
it). Decision: skip the `docs/Makefile` — the root target is already
correct and the Simplicity Principle says no indirection.

**Makefile targets**: the existing `docs` and `docs-view` targets in the
root Makefile are already correct. No Makefile changes needed.

### G. Links strategy (README → docs, works on PyPI)

**PyPI constraint** (owner): "references to files in the repo don't work"
on PyPI because the README is bundled but the repo files are not.

**Strategy:**
- All README cross-references to docs content use the **absolute ReadTheDocs
  URL** (`https://yoker-assistant.readthedocs.io/en/latest/tutorial.html`,
  etc.). This works identically on GitHub and on PyPI.
- README references to repo files that are front-door-critical
  (`yoker.toml.example`, `.env.example`, `SECURITY.md`, `TODO.md`) stay as
  repo-relative paths — these are links a reader follows after cloning, not
  after reading the PyPI page. (PyPI readers who want the examples get them
  from the ReadTheDocs configuration page, which has the same content.)
- The `Documentation` section in the README is the single hand-off: one
  absolute ReadTheDocs link.
- Inside `docs/`, cross-references use Sphinx/MyST relative refs
  (`{doc}`tutorial``) — these resolve at build time and become absolute
  URLs on ReadTheDocs.

**ReadTheDocs project URL**: `yoker-assistant.readthedocs.io` (to be
claimed on readthedocs.org; the `.readthedocs.yaml` in the repo is what
enables the build once the project is connected). Until the project is
connected, the absolute URLs will 404 — that is acceptable for the first
docs PR (the owner can enable ReadTheDocs after merge).

## Acceptance criteria coverage map (revised)

| Acceptance criterion | Where it lives now |
|---|---|
| Why this exists (c3 heritage, email-loop insight) | `docs/tutorial.md` §1 |
| The two halves (Python loop vs agent reasoning) | `docs/tutorial.md` §2 |
| The yoker SDK seam | `docs/tutorial.md` §3, `docs/architecture.md` |
| The simple-email-gw seam | `docs/tutorial.md` §3, `docs/architecture.md` |
| The handoff contract | `docs/tutorial.md` §4, `docs/architecture.md` |
| The bounded tool set and the safety model | `docs/tutorial.md` §5 |
| Configuration | `README.md` (condensed) + `docs/configuration.md` (full) |
| Running it | `README.md` "Running it" + `docs/quickstart.md` |
| The c3 → yoker-assistant porting map | `docs/tutorial.md` §6 (narrative) + `docs/porting-map.md` (full table) |
| Persistent-session architecture | `docs/tutorial.md` §7, `docs/architecture.md` |
| Custom md→html tool story | `docs/tutorial.md` §8, `docs/architecture.md` |
| Dual-mode architecture | `docs/tutorial.md` §9, `docs/architecture.md` |
| Git commit/push demo beat | `docs/tutorial.md` §10 |
| Recipient safety | `docs/tutorial.md` §11, `docs/security.md` |
| Security configuration (a) blast radius + version pinning | `README.md` "Security configuration" + `docs/security.md` |
| Security configuration (b) `EMAIL_RECIPIENT_WHITELIST_ADDRESSES` | `README.md` + `docs/security.md` + `docs/tutorial.md` §11 |
| Security configuration (c) `~/.yoker.toml`/`.env` never committed | `README.md` (new bullet) + `docs/security.md` |
| Use `c3:readme` for structure and badges | Applied to README at implementation time |
| New reader can set it up and run `python -m yoker_assistant --once` | `README.md` "Quick start" + `docs/quickstart.md` |
| Porting map explicit about kept/removed/reworked | `docs/porting-map.md` (full per-element) |
| Persistent-session, custom-tool, git-demo each explained as build decisions | `docs/tutorial.md` §7, §8, §10 |
| Tutorial is all-inclusive narrative, not reduced links | `docs/tutorial.md` — full prose throughout |
| README references docs pages (works on PyPI) | `README.md` "Documentation" section, absolute ReadTheDocs URLs |

## Standards improvement note

The owner asked: "If this wasn't clear from our standard project setup
procedures, we need to improve this."

**Finding:** The standard IS clear and documented in two places:
- `c3:documentation` skill (`/Users/xtof/Workspace/agentic/c3/skills/documentation/SKILL.md`)
- `end-user-documenter` agent (`/Users/xtof/Workspace/agentic/c3/agents/end-user-documenter.md`)

Both explicitly define the `docs/` + Sphinx + ReadTheDocs approach and the
README-as-front-door role. The original P4-001 plan did not consult either
of these — it treated the README as the sole documentation surface, which is
NOT what the standard says. This is a procedural miss, not a standards gap.

**Follow-up (separate from this PR, flagged for the c3 skills):**
- Consider adding a one-line pointer in `c3:readme` (the skill the original
  plan cited) that says "README is the front-door; full documentation lives
  in `docs/` — see `c3:documentation`." This would prevent the same miss
  when the next agent only consults `c3:readme`. The `c3:readme` skill
  already says "concise introduction with just enough examples" but does
  not currently cross-reference `c3:documentation`.
- This is a c3-skills improvement, NOT a blocker for P4-001. File it as a
  separate TODO (e.g., under `c3/skills/readme/` as an issue or a
  `lessons-learned` entry).

## Estimated length

- **README.md**: 120–180 lines (lean front-door — quick start, condensed
  config, security configuration, running it, one docs link, license).
- **docs/tutorial.md**: 600–800 lines (full all-inclusive narrative).
- **docs/architecture.md**: 400–600 lines (full seam-by-seam reference).
- **docs/porting-map.md**: 150–250 lines (full per-element table).
- **docs/security.md**: 150–250 lines.
- **docs/configuration.md**: 100–200 lines.
- **docs/installation.md**: 80–150 lines.
- **docs/quickstart.md**: 80–150 lines.
- **docs/api.md**: 100–200 lines (autodoc-assisted).
- **docs/changelog.md**: 40–80 lines (seeded, grows over time).
- **docs/index.md**: 30–50 lines.
- **`docs/conf.py`**: ~25 lines.
- **`.readthedocs.yaml`**: ~15 lines.

**Total docs/ target: ~1,900–2,800 lines across all pages.** This is
larger than the original 450–600-line single-README plan, which is the
point — the owner explicitly asked for all-inclusive, not reduced.

## Out of scope for this plan

- Writing the docs themselves (this plan is the deliverable for this step;
  implementation is a separate step).
- Editing `analysis/functional.md` (already up to date per P1-003 errata).
- Editing `SECURITY.md` (already complete per S-01). The `docs/security.md`
  page links to `SECURITY.md` (or transcludes its content); the source
  `SECURITY.md` is not modified.
- Any code changes (P4-001 is docs-only).
- The `make run-demo` target (TODO.md "Unsorted" — not P4-001).
- Enabling ReadTheDocs on readthedocs.org (owner action after PR merge; the
  `.readthedocs.yaml` in the repo is what enables the build once connected).
- The c3-skills improvement (filed as a separate follow-up, see Standards
  Improvement Note).