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

- [x] **P1-003: P1-002 errata + functional.md corrections** ✅ (2026-07-20, PR #3)
  - **DESCOPED.** The original P1-003 scope (a `Mailbox` wrapper class over
    `simple_email_gw`'s async `IMAPClient`/`SMTPClient`) was descoped per
    owner feedback — wrapping two existing classes in a thin indirection
    class added no benefit for a demo/tutorial. The loop (P2-005) calls
    `simple_email_gw` directly (constructs `IMAPClient(account)` +
    `SMTPClient(account)`, `await imap.connect()` once, polls, fetches,
    replies via `smtp.reply_email(...)`, marks read, archives,
    `await imap.disconnect()` on shutdown). No `mailbox.py`, no seam
    methods, no `__aenter__`/`__aexit__`, no `connect()`/`close()` on a
    wrapper object.
  - The task is now ONLY the errata fixes landed alongside the descope:
    - **P1-002 errata:** rename `EMAIL_RECIPIENT_ADDRESSES` →
      `EMAIL_RECIPIENT_WHITELIST_ADDRESSES` in `.env.example` and `README.md`
      (the documented env var name was wrong; `simple_email_gw` binds
      `EMAIL_RECIPIENT_WHITELIST_ADDRESSES`, and the wrong name silently
      disables the whitelist).
    - **functional.md corrections:** §2.2 (the seam is the loop module
      itself, not a wrapper class), §2.4 (no `Mailbox` wrapper; the loop
      calls `IMAPClient`/`SMTPClient` directly with explicit
      `connect()`/`disconnect()`; the errata about `simple_email_gw` 0.3.0
      clients not being async context managers stays), §4.3 (every send is
      a reply — always `reply_email`, no `send_email` fallback; reply sent
      only if the agent produced a non-empty reply body; `html_body=`
      routing clarification retained), §4.4 (the ordering is owned by the
      loop, not a `Mailbox` seam).
  - **Note (original scope, retained for the historical record):** the
    cross-domain review consensus design was a `Mailbox` class with
    `connect()`/`unread_ids()`/`fetch()`/`reply()`/`mark_read()`/`archive()`/`close()`,
    a typed `EmailMessage` dataclass, and a `reply()` that branched between
    `reply_email` and `send_email` on `in_reply_to` presence. The owner
    challenged this during PR review ("Why wrap two existing classes in
    another class with no added benefit?" / "How can the reply ever not be
    a reply?") and the consensus was descoped to errata only. See
    `reporting/p1-003/consensus.md` for the descope update and the
    original consensus design.
  - **Acceptance:** `.env.example` and `README.md` use
    `EMAIL_RECIPIENT_WHITELIST_ADDRESSES`; `analysis/functional.md` §2.2,
    §2.4, §4.3, and §4.4 reflect the descope (no `Mailbox` class; every
    send is `reply_email`; the loop owns the ordering and the
    gateway-lifecycle calls); no `mailbox.py` is created.
  - **Satisfies:** simple-email-gw integration (errata only)

### P1 — yoker SDK integration

- [x] **P1-004: Agent construction + one-time session setup** ✅ (2026-07-21, PR #4)
  - **No `Assistant` wrapper class.** The loop (P2-005) constructs yoker's
    `Agent` directly. There is no `agent.py` module that wraps `Agent` in
    another class — such a wrapper would add no behavior beyond
    configuration in `__init__` and forwarding `process()` unchanged, and
    fails the Wrapper Check.
  - The `Agent` is constructed **ONCE** at startup with a **persistent
    context manager**: `Agent(agent_path="agents/assistant.md",
    context_manager=Persisted(SimpleContextManager(),
    session_id="yoker-assistant"))`. The same session lives for the whole
    package run; each `process()` call is the next user message in that
    session. Do NOT construct a fresh `Agent`/context per email.
  - The one-time session-setup turn is **inlined in the loop** as
    `await agent.process(_INITIALIZE_PROMPT)` (a module-level constant for
    the initialize prompt) before the poll loop begins. The agent reads
    `PERSONAL.md` (via `yoker:read`) on that first turn and initializes
    identity for the ongoing session. No `setup()` method on a wrapper.
  - `agent.py` either disappears entirely (the two lines above live
    directly in `__main__.py`/`loop.py`) or shrinks to **module-level
    constants** (`_INITIALIZE_PROMPT`) plus optionally a factory function
    `make_agent(agent_path) -> Agent` that returns the configured `Agent`
    instance — no class, no forwarding methods. The factory is only
    warranted if the wiring (context manager + agent_path + any future
    config) grows past a one-liner; otherwise inline it.
  - **Note (original scope, retained for the historical record):** the
    original P1-004 design proposed an `Assistant(agent_path)` class in
    `yoker_assistant/agent.py` with `async def process(email_message) ->
    str` forwarding to `Agent.process()` and a `setup()` step forwarding
    to `Agent.process(_INITIALIZE_PROMPT)`. The owner challenged this as
    the same useless-wrapper pattern caught earlier on P1-003's `Mailbox`
    ("what behavior does this class add beyond configuration and
    forwarding?"). The answer was nothing — the wrapper earned no
    behavior — so it was descoped. The loop now constructs `Agent`
    directly; the one-time setup is an inlined `await
    agent.process(_INITIALIZE_PROMPT)`. See P1-003's descope note for the
    antecedent pattern.
  - **Acceptance:** the loop constructs `Agent` directly (no `Assistant`
    class exists in the package); `await agent.process("test")` returns a
    string using a real backend (or is mockable for tests via an `Agent`
    stub); a second `process()` call sees the first call's context
    (persistent session via `Persisted(SimpleContextManager(),
    session_id="yoker-assistant")`); the one-time setup turn is `await
    agent.process(_INITIALIZE_PROMPT)` inlined in the loop, not a method
    on a wrapper object; no email/IMAP references in this module/section.
  - **Satisfies:** yoker SDK seam

### P2 — Port the agent definition

- [x] **P2-001: Port the assistant agent definition** ✅ (2026-07-22, PR #5)
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

- [ ] **P2-002: Evaluate pa-inbox concepts and optionally split off skill sub-workflows**
  - **NOT a port.** The old `../c3/skills/pa-inbox/SKILL.md` is "old" — it
    targets the old assistant operating with an `inbox/` folder and files,
    before the assistant had access to an actual email account. Evaluate the
    concepts captured in it (item categorization rules, project detection,
    clarity indicators, memory integration) and consider which are
    applicable to the new assistant agent's definition to improve it.
    Optionally, split off parts of the new agent definition into on-demand
    skill sub-workflows to simplify it and to separate optional paths in
    the workflow into on-demand skill sub-workflows.
  - **To be considered at that time** — this task is in the backlog; the
    evaluation happens when this task is picked up, not now.
  - **Acceptance:** the evaluation is documented (which concepts apply, which
    don't, and why); any skill sub-workflow split off from the agent
    definition loads under `yoker:skill`; the agent definition is simplified
    where applicable.
  - **Satisfies:** port skills (reframed as evaluation)

- [ ] **P2-003: Evaluate pa-outbox concepts and optionally split off skill sub-workflows**
  - **NOT a port.** The old `../c3/skills/pa-outbox/SKILL.md` is "old" — it
    targets the old assistant's file-based outbox workflow. Evaluate the
    concepts captured in it (reply format: Actions Taken, Memory Created,
    Status, Pending Questions; clarification vs resolution reply types) and
    consider which are applicable to the new assistant agent's definition
    to improve it. Optionally, split off parts of the new agent definition
    (e.g. the reply-format guidance) into an on-demand skill sub-workflow
    to simplify the agent definition and separate optional paths in the
    workflow into on-demand skill sub-workflows.
  - **To be considered at that time** — this task is in the backlog; the
    evaluation happens when this task is picked up, not now.
  - **Acceptance:** the evaluation is documented (which concepts apply, which
    don't, and why); any skill sub-workflow split off from the agent
    definition loads under `yoker:skill`; the agent definition is simplified
    where applicable.
  - **Satisfies:** port skills (reframed as evaluation)

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

- [x] **P2-008: Implement the markdown→HTML converter as a yoker tool** ✅ (2026-07-22, PR #6)
  - Create a custom local tool `md_to_html` exposed as a yoker plugin/tool
    defined in THIS package (not a yoker built-in). Define it in
    `src/yoker_assistant/tools.py` as a plain Python function annotated with
    yoker tool guardrails (`Annotated[str, Text(...)]`). Expose it via
    `__YOKER_MANIFEST__ = PluginManifest(tools=[md_to_html])` in
    `src/yoker_assistant/__init__.py`. Register it via the package's own
    `yoker.toml [plugins]` (NOT programmatic — no `plugins=()` arg to
    `Agent`).
  - **Owner instruction (PR #5 review):** the `md_to_html` tool already
    exists as `c3/bin/md-to-html.py` (used by the current c3 assistant via
    the `pa-email` skill). Don't reinvent the wheel — reuse the existing
    conversion logic. P2-008's implementation should reuse/import/vendor
    the core conversion from `c3/bin/md-to-html.py`, not write a new
    converter from scratch.
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

- [x] **P2-009: Verify dual-mode / external plugin load** ✅ (2026-07-22, verified)
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

- [x] **P2-005: Implement the main loop** ✅ (2026-07-23, PR #7 — combined implementation per owner directive)
  - Create `yoker_assistant/__main__.py` (and `loop.py` if separated):
    - `async def run()`: build `EmailAccount`, construct the `Agent`
      **ONCE** directly (per P1-004 — no `Assistant` wrapper):
      `agent = Agent(agent_path="agents/assistant.md",
      context_manager=Persisted(SimpleContextManager(),
      session_id="yoker-assistant"))`, and the `simple_email_gw` clients
      directly — `imap = IMAPClient(account)`,
      `smtp = SMTPClient(account)`. Run the one-time session-setup turn
      inlined: `await agent.process(_INITIALIZE_PROMPT)` (the agent reads
      `PERSONAL.md` via `yoker:read` and initializes identity on the first
      turn); then `await imap.connect()` once and enter the loop.
    - Per iteration: `await imap.search(folder="INBOX", criteria="UNSEEN")`
      → for each id: `await imap.fetch_message(...)` → build the handoff
      payload (P2-006) → `reply_html = await agent.process(message)` (next
      message in the SAME session) → if `reply_html` is non-empty, send the
      reply via `await smtp.reply_email(to=sender,
      subject=f"Re: {subject}", html_body=reply_html,
      in_reply_to=msg["message_id"])` → `await imap.mark_message(...,
      "\\Seen", "add")` → `await imap.move_message(..., "Archive")`.
    - **Every send is a reply** — always `smtp.reply_email(...)`; there is
      no `send_email` fallback. The `Re:` subject string and the
      `in_reply_to=msg["message_id"]` passthrough are loop-side
      one-liners. The `html_body=` kwarg name is the loop's responsibility
      (it routes the agent's HTML through `simple_email_gw`'s HTML
      content-type path); the loop does NOT construct MIME itself.
    - If the agent returns an empty reply body, the loop SKIPS the send
      (and the message-handling decision in that case — whether to mark
      read, archive, or retry — is a loop concern, see §4.3/§7).
    - **No `Mailbox` object.** The loop owns the gateway lifecycle
      explicitly: `await imap.connect()` once at startup,
      `await imap.disconnect()` on shutdown; `smtp.connect()`/`smtp.disconnect()`
      around the send (or once for the loop's lifetime — implementation
      choice). The ordering (send → mark read → archive) lives in the loop
      (§4.4), not in a seam object.
    - The `Agent` is constructed ONCE at startup with a persistent context
      manager; the loop delivers each email as the next user message to that
      session. Do NOT construct a fresh Agent per email.
    - `--once` flag: process one iteration and exit.
    - Graceful shutdown on `SIGINT`/`SIGTERM`: finish in-flight message,
      `await imap.disconnect()` (and `smtp.disconnect()` if held open),
      exit 0.
    - Error handling per §7 of the analysis: connection failure backs off;
      agent/send failure does not mark read; per-message exceptions skip and
      continue.
  - **Note (Wrapper Check):** the loop itself is multi-step orchestration
    (poll → fetch → process → reply → mark → archive) — that IS earned
    behavior, not a wrapper. No sub-wrappers are introduced inside it:
    `Agent`, `IMAPClient`, `SMTPClient`, and `build_message` are all
    called directly.
  - **Acceptance:** `python -m yoker_assistant --once` runs one poll and exits
    cleanly on an empty inbox; a seeded unread email produces a reply (with a
    live backend) and is marked read + archived; the reply is sent via
    `smtp.reply_email(..., html_body=reply_html, in_reply_to=msg["message_id"])`
    (not `send_email`, not `body=`); when the agent produces no reply body,
    no send is attempted; a second email in a subsequent iteration sees the
    first email's context (persistent session).
  - **Satisfies:** the loop

### P2 — The handoff contract

- [x] **P2-006: Implement the handoff payload builder** ✅ (2026-07-23, PR #7 — combined implementation per owner directive)
  - Create `yoker_assistant/handoff.py`: `build_message(email_message) -> str`
    producing the §4.1 format — **only** `From`/`Subject`/`Date` headers + body.
    NO instructions block. Identity/instructions live in the agent definition
    (system prompt) and the one-time session-setup step, not in the per-email
    payload. Pure function, no I/O.
  - **Scope update (post-P1-003 functional-analyst review):** the slim P1-003
    implementation dropped the `EmailMessage` dataclass — the loop's
    `await imap.fetch_message(id, folder="INBOX")` returns the raw
    `simple_email_gw` message dict directly. `build_message` therefore
    accepts the raw `simple_email_gw` message dict (not an `EmailMessage`
    dataclass) and reads the fields it needs directly from the dict (e.g.
    `msg["subject"]`, `msg["from"]`, `msg["date"]`, `msg["body"]`). Reference
    the `simple_email_gw` `fetch_message` dict shape as the shared contract.
  - The session-setup step (agent reads `PERSONAL.md` and initializes) is run
    once at startup in the loop (P2-005), not here.
  - **Acceptance:** given a fetched `simple_email_gw` message dict, returns
    the exact payload string (headers + body, no `Instructions:` block);
    unit-testable with a fixture dict matching the gateway's `fetch_message`
    shape.
  - **Satisfies:** handoff contract

- [ ] **P2-007: Wire reply sending with correct threading (HTML)** —
  FOLDED INTO P2-005
  - **No remaining scope.** The reply sending is a single
    `smtp.reply_email(...)` call in the loop (P2-005). The `Re:` subject
    string and the `in_reply_to=msg["message_id"]` passthrough are
    loop-side one-liners already specified in P2-005. The `send_email`
    fallback has been dropped — every send is a reply (always
    `reply_email`). The `html_body=` routing is a loop concern (kwarg
    name), also specified in P2-005.
  - **Original scope (retained for the historical record):** wire
    `Mailbox.reply()` with the `in_reply_to` branch (`reply_email` vs
    `send_email` fallback) and the `html_body=` forwarding. That branch and
    the `Mailbox` seam were descoped per owner feedback; the loop now does
    the single `reply_email` call directly.
  - **Acceptance:** covered by P2-005's acceptance criteria (the loop
    sends via `smtp.reply_email(..., html_body=reply_html,
    in_reply_to=msg["message_id"])`).
  - **Satisfies:** handoff contract (folded into P2-005)

### P3 — Tests

- [ ] **P3-001: Tests for the handoff contract**
  - `tests/test_handoff.py`: assert `build_message` produces the documented
    format for a representative message (From/Subject/Date headers + body
    present; NO `Instructions:` block).
  - **Acceptance:** `make test` passes; covers the contract that would
    regress if the format changed.
  - **Satisfies:** tests (handoff)

- [ ] **P3-002: Tests for the polling logic**
  - `tests/test_loop.py`: with fake `IMAPClient`/`SMTPClient` stubs (no
    network) and a fake `Agent` (no backend — a stub that returns a canned
    reply string from `process()`), assert the loop:
    fetches unseen, calls `process`, sends the reply via
    `smtp.reply_email(..., html_body=<agent output>, in_reply_to=msg["message_id"])`
    (NOT `body=`, NOT `send_email`), marks read, archives, in order;
    on empty inbox sleeps and does not error; on agent failure does not
    mark read; on send failure does not archive; **and when the agent
    returns an empty reply body, the loop skips the send entirely** (no
    `reply_email` call, no mark-read, per §4.3).
  - **html_body= routing regression test (absorbed from the descoped
    P1-003 `test_mailbox.py`):** P3-002 MUST assert the loop calls
    `smtp.reply_email` with `html_body=<agent output>` (not `body=`), so
    the reply renders as HTML in the recipient's client. This is the
    regression test that guarded the `html_body=` routing when the
    `Mailbox` seam existed; with the seam descoped, the routing is a
    loop-side concern and the test lives here.
  - **Acceptance:** `make test` passes; behavior-based, no real
    IMAP/LLM; the `html_body=` routing is asserted at the loop→gateway
    boundary; the skip-on-empty-reply-body behaviour is asserted.
  - **Satisfies:** tests (polling + html_body= routing)

- [ ] ~~**P3-003: Tests for the mailbox seam**~~ — DROPPED
  - **Dropped — P1-003's `Mailbox` seam was descoped.** There is no seam
    module to test. The `html_body=` routing regression test that lived
    in the descoped `test_mailbox.py` has been absorbed into P3-002
    (loop tests), where the loop→gateway boundary is now exercised
    directly.

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
  - **Implement as a Makefile target, not a Python wrapper module.** The
    guard is two shell steps over `make build` output: `twine check dist/*`
    plus a grep of the built `METADATA` file for `file:` / `@ file://`.
    No Python class, no adapter, no façade — a Makefile recipe is the
    right-sized home for "run two commands and fail on grep hit." A
    Python wrapper around `twine check` + `grep` would add no behavior
    beyond forwarding and fails the Wrapper Check.
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
    option (`EMAIL_RECIPIENT_WHITELIST_ADDRESSES`), not package code.
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