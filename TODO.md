# TODO

Backlog for the yoker-assistant first pass (Phase 1A). Ordered: bootstrap →
simple-email-gw integration → yoker SDK integration → port agent → port
skills → custom md→html tool → the loop → handoff contract → tests → docs
(tutorial). One custom bounded tool (the markdown→HTML converter) IS in
scope as the showcase's "create your own bounded tool" example; all other
new bounded tools remain Phase B and are deliberately absent.

## Backlog (Prioritized)

### P1 — Bootstrap & project skeleton

- [x] **P1-001: Initialize uv Python project structure** ✅ (2026-07-19, PR #1)
  - Create `pyproject.toml` (uv-managed) with package metadata, Python
    version, and the standard Makefile targets per `c3:python-project`
    (build, check, clean, env-dev, env-run, format, help, lint, pre-publish,
    publish, run, test-all, test-cov, test, typecheck).
  - Source layout: `src/yoker_assistant/`.
  - Entry point: console script `yoker-assistant` → `yoker_assistant.__main__`.
  - **Acceptance:** `make help` lists targets; `make env-dev` installs; `make
    test` runs with zero tests passing; `python -m yoker_assistant` imports
    without error (exits cleanly when no config).
  - **Satisfies:** bootstrap

- [x] **P1-002: Add runtime dependencies** ✅ (2026-07-20, PR #2)
  - Depend on `yoker` (local path or PyPI), `simple-email-gw`, and `pkgq`
    (plugin). Document local-path wiring for development
    (`../yoker`, `../simple-email-gw`).
  - **Local-path dev-wiring mechanism (security-engineer recommendation,
    blocking):** keep `[project.dependencies]` as PyPI names only — NEVER
    add `file://`/`path =` entries to `[project.dependencies]` (they would
    leak into published sdist/wheel metadata and corrupt installability).
    Express local-path dev wiring via `[tool.uv.sources]` (uv-native,
    dev-only, structurally excluded from wheel/sdist metadata):
    ```
    [tool.uv.sources]
    yoker = { path = "../yoker", editable = true }
    simple-email-gw = { path = "../simple-email-gw", editable = true }
    ```
    This is the intended mechanism — the structural exclusion from PyPI
    metadata is the safety property, not contributor discipline.
  - Document the required user config in `~/.yoker.toml`: `[plugins] enabled
    = true; packages = ["yoker_assistant", "pkgq"]` and `[plugins.trusted]
    yoker_assistant = true; pkgq = true` (self-trust is REQUIRED for
    unattended operation — with no TTY to prompt, the trust gate rejects
    untrusted plugins in non-interactive mode), `skills.directories =
    ["./skills"]`. Provide a `yoker.toml.example` as reference documentation
    (not a checked-in active config). yoker resolves config from `~/.yoker.toml`
    (user) and `./yoker.toml` (cwd), NOT from the package install location —
    so a repo-level `yoker.toml` is only read during local dev and would
    clobber the user's backend config. The user's `~/.yoker.toml` is the
    correct location for plugin registration.
  - Add `.env.example` for email account config.
  - **Acceptance:** `make env-dev` resolves all deps; the README documents
    the required `~/.yoker.toml` lines; a `yoker.toml.example` is provided
    as reference with a REFERENCE ONLY header and no real `api_key`;
    `make pre-publish` (or equivalent) confirms no `file://`/path deps
    leak into the built sdist/wheel metadata.
  - **Satisfies:** bootstrap

### P1 — simple-email-gw integration

- [ ] **P1-003: Implement the mailbox seam module**
  - Create `yoker_assistant/mailbox.py` wrapping `simple_email_gw`'s async
    `IMAPClient`/`SMTPClient`. Expose a small, typed surface:
    `Mailbox(account)` with `connect()`, `unread_ids()`, `fetch(id)`,
    `reply(to, subject, html_body, in_reply_to, *, text_body='')`,
    `mark_read(id)`, `archive(id)`, `close()`.
  - No business logic here — pure seam. Configuration via `EmailAccount` from
    env/`.env`.
  - **Scope/contract (cross-domain review consensus):**
    - Mailbox is a thin async seam, long-lived: construct once, `await
      connect()` once, `await close()` on shutdown; implements
      `__aenter__`/`__aexit__`. Holds one IMAPClient + one SMTPClient.
      simple_email_gw 0.3.0 clients are NOT async context managers
      themselves.
    - `fetch()` returns a typed `EmailMessage` dataclass (frozen, slots) with
      fields: `id`, `subject`, `from_`, `to`, `date`, `body` (plain text),
      `message_id` (RFC Message-ID; `''` if absent), `references`
      (tuple[str,...]), `read`. This is the shared contract for P2-006
      (handoff builder) and P3-003 (tests).
    - `reply(to, subject, html_body, in_reply_to, *, text_body='')` — the
      HTML parameter is named `html_body` to make routing to
      simple_email_gw's `html_body=` explicit. `text_body` is the optional
      plain-text alternative (intentionally empty in the first pass;
      accessibility polish deferred).
    - Constructor: `Mailbox(account, *, inbox_folder='INBOX',
      archive_folder='Archive', imap_client=None, smtp_client=None)`. The
      `imap_client`/`smtp_client` kwargs are for P3-003 dependency-injected
      stubs.
    - The seam does NOT swallow or retry connection/send failures — it
      propagates exceptions from simple_email_gw so the loop's §7
      backoff/skip policy handles them.
    - The seam constructs `EmailAccount` via simple_email_gw's
      `ServerConfig`/`get_accounts()` (inherits TLS 1.2+ with cert
      verification; refuse/loudly warn on plaintext-credential configs).
    - The seam does NOT reinvent the recipient allowlist — reply sending
      delegates to simple_email_gw which enforces
      `EMAIL_RECIPIENT_WHITELIST_ADDRESSES`.
    - The seam must NOT call `get_secret_value()` outside gateway calls;
      `EmailAccount.password` is a pydantic `SecretStr`;
      `Mailbox.__repr__` redacts credentials.
    - Logging posture: INFO counts/events only (e.g. "fetched N unseen");
      never message bodies, credentials, or full headers.
  - **Acceptance:** module imports; each method delegates to exactly one
    `simple_email_gw` call, except `reply()` which branches between
    `reply_email` and `send_email` on `in_reply_to` presence (transport
    routing, not business logic); no inline agent/reasoning logic.
  - **Blocking acceptance checks (cross-domain review):**
    - `reply()` routes the agent's HTML through simple_email_gw's
      `html_body=` parameter (not `body=`), so the reply renders as HTML in
      the recipient's client.
    - At startup (seam or loop init), assert
      `get_recipient_whitelist().enabled is True` and non-empty — fail
      closed for unattended operation (no silent reply-to-arbitrary-senders).
  - **P1-002 errata (lands alongside P1-003):** rename
    `EMAIL_RECIPIENT_ADDRESSES` →
    `EMAIL_RECIPIENT_WHITELIST_ADDRESSES` in `.env.example` and `README.md`
    (the documented env var name was wrong; simple_email_gw binds
    `EMAIL_RECIPIENT_WHITELIST_ADDRESSES`, and the wrong name silently
    disables the whitelist).
  - **Satisfies:** simple-email-gw seam

### P1 — yoker SDK integration

- [ ] **P1-004: Implement the agent seam module**
  - Create `yoker_assistant/agent.py` wrapping yoker's `Agent`. Expose
    `Assistant(agent_path)` with `async def process(email_message) -> str`.
  - The `Agent` is constructed **ONCE** at startup with a **persistent
    context manager** (yoker's `PersistenceContextManager` or equivalent).
    The same session lives for the whole package run; each `process()` call
    is the next user message in that session. Do NOT construct a fresh
    `Agent`/context per email.
  - Expose a `setup()` step run once at startup: the agent reads
    `PERSONAL.md` (via `yoker:read`) and initializes identity for the
    ongoing session.
  - **Acceptance:** `Assistant.process("test")` returns a string using a real
    backend (or is mockable for tests); a second `process()` call sees the
    first call's context (persistent session); no email/IMAP references in
    this module.
  - **Satisfies:** yoker SDK seam

### P2 — Port the agent definition

- [ ] **P2-001: Port the assistant agent definition**
  - Create `agents/assistant.md` from `../c3/agents/assistant.md`:
    - **Keep** concept, workflow phases (Initialize → Process → Reply →
      Update), categorization rules, memory/personalization guidance.
    - **Keep** the PERSONAL.md read/write behaviour AS-IS from c3: the
      definition instructs the agent to read `PERSONAL.md` at session start
      (via `yoker:read`) AND to write learned behaviours to it (via
      `yoker:update`/`yoker:write`) for later.
    - **Remove** the entire "Email Operations" section, the "Use MCP tools
      for email" guardrail, the c3-specific skill-priority table, and the
      `color` frontmatter field.
    - **Rework** the `tools:` frontmatter to the bounded yoker set: `read`,
      `list`, `search`, `write`, `update`, `websearch`, `webfetch`, `skill`,
      `agent`, `git` (**full git**: read + commit + push), `pkgq:find`,
      and `yoker_assistant:md_to_html` (the custom local tool from P2-008).
    - **ERRATA (pkgq tool name — api-architect review of P1-002):** the
      published `pkgq` yoker plugin exposes its package-finder tool as
      **`pkgq:find`**, NOT `pkgq:find_package`. The `find_package` name is
      the MCP-server tool surface (a different integration), not the yoker
      plugin tool. Use `pkgq:find` in the `agents/assistant.md` `tools:`
      frontmatter. `functional.md` §3.2 and §3.3 currently say
      `pkgq:find_package` — this is an errata in the analysis document and
      will be corrected when P2-001 is implemented (the same edit that ports
      the agent definition updates §3.2/§3.3 to `pkgq:find`).
    - Rewrite the "Process" and "Reply" phases to fit the persistent-session
      email handoff: each email is the next user message in an ongoing
      session; the reply is composed in markdown then converted to HTML via
      the `md_to_html` tool; no outbox files.
  - **Acceptance:** `Agent(agent_path="agents/assistant.md")` loads; declared
    tools all resolve (yoker logs no missing-tool warnings — in particular
    `pkgq:find` resolves; `pkgq:find_package` would NOT resolve and must
    not appear); the definition contains no `mcp__` references and no
    `Bash`; the definition instructs reading `PERSONAL.md` at session start
    and permits writing to it.
  - **Satisfies:** port agent

### P2 — Port the skills

- [ ] **P2-002: Port pa-inbox skill (reworked)**
  - Create `skills/pa-inbox/SKILL.md` from `../c3/skills/pa-inbox/SKILL.md`:
    - **Keep** item categorization rules, project detection, clarity
      indicators, memory integration.
    - **Remove** all file I/O steps (list `inbox/`, move to `inbox/archive/`,
      write `outbox/` files, `re-` naming).
    - **Rework** the workflow to: given the email content in the handoff,
      categorize each item, take actions with the agent's tools, and produce
      reply content. No mailbox mechanics.
  - **Acceptance:** skill loads under `yoker:skill`; body references no
    `inbox/` or `outbox/` directories.
  - **Satisfies:** port skills

- [ ] **P2-003: Port pa-outbox skill (reworked)**
  - Create `skills/pa-outbox/SKILL.md` from `../c3/skills/pa-outbox/SKILL.md`:
    - **Keep** reply format (Actions Taken, Memory Created, Status, Pending
      Questions), clarification vs resolution reply types.
    - **Remove** outbox file writing, archive management, markdown-to-HTML
      conversion.
  - **Acceptance:** skill loads; the agent's reply text follows the kept
    format; no filesystem reply-writing instructions.
  - **Satisfies:** port skills

- [ ] **P2-004: Record decision to drop pa-session**
  - Decision: DROP `pa-session` entirely. yoker's persistent context manager
    (used by P1-004/P2-005) carries session state natively across `process()`
    calls — the agent remembers the running conversation across emails without
    an external state file. On top of that, the agent writes memory files and
    `PERSONAL.md` learned behaviours (committed via `yoker:git`). There is no
    job left for `pa-session`.
  - Document the rationale in `analysis/functional.md` §3.4 (already done).
  - **Acceptance:** no `skills/pa-session/` is created; the analysis §3.4
    records the drop and the why.
  - **Satisfies:** port skills

### P2 — Custom tool

- [ ] **P2-008: Implement the markdown→HTML converter as a yoker tool**
  - Create a custom local tool `md_to_html` exposed as a yoker plugin/tool
    defined in THIS package (not a yoker built-in). Define it in
    `src/yoker_assistant/tools.py` as a plain Python function annotated with
    yoker tool guardrails (`Annotated[str, Text(...)]`). Expose it via
    `__YOKER_MANIFEST__ = PluginManifest(tools=[md_to_html])` in
    `src/yoker_assistant/__init__.py`. Register it via the package's own
    `yoker.toml [plugins]` (NOT programmatic — no `plugins=()` arg to
    `Agent`).
  - **`__init__.py` discipline:** `__init__.py` must ONLY define the
    manifest and import tool functions — NO `Agent` construction or loop
    logic there (that lives in `__main__`/`loop`/`agent` modules). This
    avoids any circular import.
  - Namespace: `yoker_assistant:md_to_html` (the package's own tool
    namespace). Loadable as a yoker tool via `yoker.toml [plugins]` with this
    package trusted.
  - This is the showcase's "create your own bounded tool" example — a named,
    safe, locally-defined tool — pairing with the built-in curated tools to
    demonstrate both halves of yoker's tool model. Because it is
    plugin-registered, any external yoker consumer can load it the same way.
  - **Acceptance:** the tool is loadable as `yoker_assistant:md_to_html` by
    the package's own agent (yoker logs no missing-tool warning when the
    agent declares it) AND by an external yoker consumer; the agent can call
    it during `process()`; given a markdown string it returns an HTML string;
    unit-tested with a representative markdown fixture.
  - **Satisfies:** custom bounded tool

- [ ] **P2-009: Verify dual-mode / external plugin load**
  - Confirm the reusable-plugin layer: a separate minimal yoker consumer
    (a tiny script or test) loads yoker-assistant as a plugin and calls
    `yoker_assistant:md_to_html`. This proves the third layer of the
    dual-mode architecture — self-load and external load use the identical
    mechanism (`pip install yoker-assistant` + `[plugins]` / `[plugins.trusted]`
    in the consumer's `yoker.toml`).
  - **Acceptance:** external load works identically to self-load; the tool
    resolves and executes under the external consumer and returns the same
    HTML output.
  - **Satisfies:** dual-mode showcase

### P2 — The loop

- [ ] **P2-005: Implement the main loop**
  - Create `yoker_assistant/__main__.py` (and `loop.py` if separated):
    - `async def run()`: build `EmailAccount`, `Mailbox`, `Assistant`; run
      the one-time session-setup step (`Assistant.setup()` — send an
      initialize message to the session so the agent reads `PERSONAL.md`
      via `yoker:read` and initializes identity on the first turn); then
      enter the loop: `unread_ids()` → for each: `fetch` → `agent.process`
      (next message in the SAME session) → `reply` → `mark_read` →
      `archive`; sleep `poll_interval`; repeat.
    - The `Agent` is constructed ONCE at startup with a persistent context
      manager; the loop delivers each email as the next user message to that
      session. Do NOT construct a fresh Agent per email.
    - `--once` flag: process one iteration and exit.
    - Graceful shutdown on `SIGINT`/`SIGTERM`: finish in-flight message,
      close connections, exit 0.
    - Error handling per §7 of the analysis: connection failure backs off;
      agent/send failure does not mark read; per-message exceptions skip and
      continue.
  - **Acceptance:** `python -m yoker_assistant --once` runs one poll and exits
    cleanly on an empty inbox; a seeded unread email produces a reply (with a
    live backend) and is marked read + archived; a second email in a
    subsequent iteration sees the first email's context (persistent session).
  - **Satisfies:** the loop

### P2 — The handoff contract

- [ ] **P2-006: Implement the handoff payload builder**
  - Create `yoker_assistant/handoff.py`: `build_message(email_message) -> str`
    producing the §4.1 format — **only** `From`/`Subject`/`Date` headers + body.
    NO instructions block. Identity/instructions live in the agent definition
    (system prompt) and the one-time session-setup step, not in the per-email
    payload. Pure function, no I/O.
  - `build_message` accepts the `EmailMessage` dataclass defined in P1-003
    (not a raw dict); reference the P1-003 `EmailMessage` fields as the
    shared contract.
  - The session-setup step (agent reads `PERSONAL.md` and initializes) is run
    once at startup in the loop (P2-005), not here.
  - **Acceptance:** given a fetched `EmailMessage`, returns the exact payload
    string (headers + body, no `Instructions:` block); unit-testable with a
    fixture.
  - **Satisfies:** handoff contract

- [ ] **P2-007: Wire reply sending with correct threading (HTML)**
  - In the loop, send via `Mailbox.reply()` using `reply_email` with
    `in_reply_to=<RFC Message-ID>` from the fetched message. Fallback to
    `send_email` with `Re: <subject>` if Message-ID is unavailable.
  - The body is **HTML** — the agent's `md_to_html`-converted output
    (returned by `agent.process()`). Set the appropriate content type for
    HTML; send the HTML verbatim, do not re-render.
  - Recipient safety is a `simple-email-gw` config concern
    (`EMAIL_RECIPIENT_ADDRESSES`), not package code. No package-level
    allowlist is written; document the gateway config in the README.
  - **Acceptance:** replies thread correctly in a mail client and render as
    HTML; the reply body is the agent's HTML output verbatim.
  - **Satisfies:** handoff contract

### P3 — Tests

- [ ] **P3-001: Tests for the handoff contract**
  - `tests/test_handoff.py`: assert `build_message` produces the documented
    format for a representative message (From/Subject/Date headers + body
    present; NO `Instructions:` block).
  - **Acceptance:** `make test` passes; covers the contract that would
    regress if the format changed.
  - **Satisfies:** tests (handoff)

- [ ] **P3-002: Tests for the polling logic**
  - `tests/test_loop.py`: with a fake `Mailbox` (no network) and a fake
    `Assistant` (no backend), assert the loop: fetches unseen, calls
    `process`, sends reply, marks read, archives, in order; on empty inbox
    sleeps and does not error; on agent failure does not mark read; on send
    failure does not archive.
  - **Acceptance:** `make test` passes; behavior-based, no real IMAP/LLM.
  - **Satisfies:** tests (polling)

- [ ] **P3-003: Tests for the mailbox seam**
  - `tests/test_mailbox.py`: a small integration test against
    `simple_email_gw`'s public surface — assert the seam methods map to the
    expected client calls (use a stub/spool or a documented test account if
    `simple-email-gw` provides one). Keep it useful, not exhaustive.
  - Stub clients injected via `Mailbox(..., imap_client=...,
    smtp_client=...)`; assert each `Mailbox` method calls the expected stub
    method with the expected arguments (DI approach, not monkeypatching).
  - **Acceptance:** `make test` passes; the seam is exercised, not just
    imported.
  - **Satisfies:** tests (mailbox seam)

### P3 — Security (defense in depth)

- [ ] **S-01: Add `SECURITY.md` describing the `__YOKER_MANIFEST__` review
  process**
  - Every addition to `__YOKER_MANIFEST__` auto-trusts on user install via
    `[plugins.trusted] yoker_assistant = true` — there is no secondary
    review gate inside the package. `SECURITY.md` documents the review
    process contributors must follow before adding a tool to the manifest
    (blast-radius assessment, capability review, version pinning).
  - **Priority rationale:** land before Phase B so the review process exists
    before any second tool is added to the manifest.
  - **Acceptance:** `SECURITY.md` exists at repo root and documents the
    manifest-addition review process; the README links to it from the
    Security configuration subsection.
  - **Satisfies:** security (manifest review process)

- [ ] **S-02: `make pre-publish` guard rejecting non-registry source URLs in
  built metadata**
  - Defense in depth: a publish-time guard that fails `make pre-publish` if
    the built sdist/wheel METADATA contains `file://`, `path =`, or any
    non-registry source URL. Prevents the P1-002 path-dep leakage class from
    ever reaching PyPI even if `[tool.uv.sources]` discipline slips.
  - Implement as a check over `make build` output: `twine check dist/*` plus
    a grep of the built `METADATA` file for `file:` / `@ file://`.
  - **Acceptance:** `make pre-publish` fails when a path/file URL is present
    in built metadata and passes when deps are PyPI names only; verified
    with a deliberate path-dep injection in a throwaway build.
  - **Satisfies:** security (publish guard)

- [ ] **S-03: File upstream issue against simple-email-gw for wrong env var
  names in its README**
  - Its README documents the wrong env var names
    (`EMAIL_RECIPIENT_ADDRESSES` vs the actual
    `EMAIL_RECIPIENT_WHITELIST_ADDRESSES` binding). Same bug affects all
    consumers.
  - **Acceptance:** an upstream issue is filed (link recorded here once
    available) describing the wrong-name docs and the silent-disable
    consequence.
  - **Satisfies:** security (upstream docs correction)

### P4 — Documentation (tutorial)

- [ ] **P4-001: Write the "how was this built?" tutorial README**
  - Per STANDARDS.md doc voice: a reader follows the journey from empty repo
    to working package and understands each decision. Cover: why this exists
    (c3 heritage, the email-loop-moved-to-Python insight), the two halves
    (Python loop vs agent reasoning), the yoker SDK seam, the simple-email-gw
    seam, the handoff contract, the bounded tool set and the safety model,
    configuration, running it, the c3 → yoker-assistant porting map.
  - **Persistent-session architecture:** explain the one long-lived agentic
    session — Agent constructed once at startup with a persistent context
    manager, each email delivered as the next user message, continuity living
    in the session plus memory files and `PERSONAL.md`.
  - **Custom md→html tool story:** explain creating your own bounded tool —
    the `yoker_assistant:md_to_html` converter as a yoker plugin/tool defined
    in this package — pairing with yoker's built-in curated tools to
    demonstrate both halves of yoker's tool model. HTML replies (not plain
    text) because markdown and email do not render well together.
  - **Dual-mode architecture:** cover the three-layer tool model — the
    package is simultaneously a consumer of yoker's built-in curated tools,
    a provider of its own named safe tool (`yoker_assistant:md_to_html`),
    and a reusable plugin any external yoker consumer can load. Explain the
    self-trust requirement for unattended operation (no TTY to prompt —
    the trust gate rejects untrusted plugins in non-interactive mode) and
    that self-consumption and third-party consumption use the identical
    mechanism (`pip install yoker-assistant` + `[plugins]` /
    `[plugins.trusted]` in `yoker.toml`).
  - **Git commit/push demo beat:** document the visible "acts on behalf of
    the owner" moment — the agent learns a behaviour, writes `PERSONAL.md`,
    commits, and pushes via full `yoker:git` (bounded tools, not a shell).
  - **Recipient safety:** document that it is a `simple-email-gw` config
    option (`EMAIL_RECIPIENT_ADDRESSES`), not package code.
  - **Security configuration subsection (security-engineer recommendation):**
    include a short "Security configuration" section covering: (a) the
    self-trust blast radius — marking `[plugins.trusted] yoker_assistant =
    true; pkgq = true` admits ALL tool code from those packages as trusted
    with no per-call gate, so users must pin the installed version
    (`uv pip install yoker-assistant==<version>`) and verify the source;
    (b) the correct env var name
    `EMAIL_RECIPIENT_WHITELIST_ADDRESSES` as the primary reply-safety
    boundary — it must be set to the single owner address or the agent
    could reply to arbitrary senders; the whitelist is silently disabled
    if unset/wrong (reply-to-arbitrary-senders risk); (c) the rule that
    `~/.yoker.toml` and `.env` are NEVER committed (`.env` is already
    gitignored; a user who snapshots `~/.yoker.toml` into a repo must
    gitignore it too).
  - Use `c3:readme` for structure and badges.
  - **Acceptance:** README tells the build story end-to-end; a new reader can
    set it up and run `python -m yoker_assistant --once`; the porting map is
    explicit about kept/removed/reworked; the persistent-session
    architecture, the custom-tool story, and the git demo beat are each
    explained as build decisions.
  - **Satisfies:** docs

## Unsorted

- HTML rendering polish / styling of the converted HTML (CSS, inline styles,
  dark-mode friendliness) — the first pass ships unstyled HTML from the
  `md_to_html` tool; styling is a later polish task.
- Attachment handling — explicitly out of scope for the first pass.
- Batch per-iteration processing (multiple emails per loop) — later
  optimization; first pass is one email per iteration.
- Multi-account email support — out of scope; single account.
- A `make run-demo` target that seeds a local mailbox and runs one iteration
  end-to-end for showcase purposes — nice to have once the loop exists.