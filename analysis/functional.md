# Functional Analysis — yoker-assistant

## 1. Project Overview & Purpose

`yoker-assistant` is a standalone Python package that demonstrates **yoker used
as a Python SDK**. It is one of two yoker 1.0 pet-store showcase packages
governed by `STANDARDS.md`; its sister project `yoker-writing-assistant`
demonstrates yoker-as-runtime. This package demonstrates yoker-as-SDK: the
Python process owns the loop and imports yoker as a library.

The package is a personal assistant that communicates **by email only**. The
owner emails it; it reasons about the email, acts on the owner's behalf using a
curated set of safe tools, and emails back. It runs **unattended** on the host
it is started on. The inbox is the entire UI: no TUI, no CLI prompts, no web.

### Why this project exists

The heritage assistant lives in `../c3/agents/assistant.md` and runs inside
Claude Code. In that model, the **agent** does the cheap recurring structured
work of polling an email inbox via an MCP email server
(`mcp__plugin_c3_email__*` tools). That is exactly the pattern this project
eliminates: the email loop moves **out of the agent into Python**, and the
agent is left to do only what it is good at — reasoning.

So the port does two things:

1. **MOVE the email loop into Python.** Python polls the mailbox via the
   `simple-email-gw` package, parses messages, and sends replies. The MCP
   email-server tools and inbox-checking logic are removed from the agent.
2. **WRAP the slimmed agent in a Python loop that calls yoker as an SDK.**
   When Python detects an email, it hands the email content plus instructions
   to the agent via yoker's `Agent.process()`. The agent reasons and replies;
   Python sends the reply via `simple-email-gw`.

### Scope of this first pass

- Port the assistant agent and its skills from c3, adapted to the yoker
  context.
- Remove the MCP-email-server logic from the agent.
- Wrap in the Python email-checking loop using `simple-email-gw` + yoker SDK.
- **One new bounded tool IS in scope:** a custom markdown→HTML converter,
  defined as a yoker plugin/tool in THIS package. This is the showcase's
  "create your own bounded tool" example — a named, safe, locally-defined
  tool — and pairs with using yoker's built-in curated tools to demonstrate
  both halves of yoker's tool model. No other new bounded tools are added
  (Phase B remains out of scope).

## 2. Architecture

### 2.1 The loop

The package runs a single long-lived agentic session. At **startup** (once):
construct the `Agent` with a **persistent context manager** and run a
session-setup step — the agent reads `PERSONAL.md` (via `yoker:read`) and
initializes its identity for the ongoing session. The package then runs for
as long as the agent runs; the Agent is constructed ONCE, not per email.

Per iteration of the async loop:

1. **Poll.** Connect to the configured mailbox via `simple-email-gw`. Search
   `INBOX` for `UNSEEN` messages.
2. **Sleep if empty.** If none, sleep for the configured poll interval and
   repeat.
3. **Fetch.** For each unseen message, fetch the full message (sender,
   subject, date, body).
4. **Handoff.** Build the per-email message (From/Subject/Date + body only —
   no instructions block; identity lives in the agent definition and the
   one-time session setup) and deliver it to the SAME session as the next
   user message via `agent.process(message)`.
5. **Reply.** Take the agent's HTML output (produced via the custom
   markdown→HTML tool) and send it verbatim as the reply email body via
   `simple-email-gw`.
6. **Settle.** Mark the message read (`\Seen`) and move it to the archive
   folder, so the next `UNSEEN` search returns only truly new messages.
7. Loop back to step 1.

The agent REMEMBERS the running conversation across emails: continuity lives
in the persistent session (yoker's context manager) plus memory files and
`PERSONAL.md` learned behaviours the agent writes.

### 2.2 The two halves do not bleed (per STANDARDS.md "tight code")

- **Python owns the cheap structured loop**: mailbox connection, search,
  fetch, reply send, mark-read, archive, sleep, error handling, shutdown.
- **The agent owns the reasoning**: categorizing email content, deciding
  what actions to take, using its curated tools to take them, composing the
  reply in markdown, and converting it to HTML via its `md_to_html` tool.
- No agent cost is spent on structured work (it never polls, never touches
  IMAP/SMTP). No Python is spent on reasoning (Python does not interpret the
  email body).
- **The seam between the two halves is the loop module itself** — the
  conceptual boundary where the structured work (Python) hands off to the
  reasoning work (the agent) and back. There is NO `Mailbox` wrapper class
  indirection layer: the loop calls `simple_email_gw`'s `IMAPClient` and
  `SMTPClient` directly (see §2.4). An earlier design proposed a `Mailbox`
  seam class; it was descoped per owner feedback (wrapping two existing
  classes in a third class added no benefit for a demo/tutorial).

### 2.3 The yoker SDK seam

Yoker is a library-first, async, event-driven agent harness. The public SDK
surface, confirmed against `yoker/examples/library_usage.py` and
`yoker/src/yoker/core/__init__..py`, is:

```python
from yoker.config import get_yoker_config
from yoker.session import Session

config = get_yoker_config()
config.agent = "yoker_assistant:assistant"  # resolved by name from the registry
# Session is constructed ONCE at startup and owns the agent registry, the
# primary Agent, persistence (via config.context), and the `agent` tool.
async with Session(config, session_id="yoker-assistant") as session:
    agent = session.agent
    # Each email is the next user message in the SAME session.
    response = await agent.process(message)  # returns the agent's text
```

Key facts of the seam:

- `Session(config, *, session_id=None, ...)` requires a `Config` object;
  config is discovered from `./yoker.toml` then `~/.yoker.toml` via
  `get_yoker_config()`. `config.agent` is set programmatically to
  `yoker_assistant:assistant` so Session resolves the assistant by name
  from the plugin-loaded `AgentRegistry` (no manual definition loader).
- `session.agent.process(message) -> str` is **async** and returns the
  agent's final text response. Tool calls happen internally during
  `process`.
- A **persistent context manager** keeps the running conversation across
  `process()` calls; the Session is constructed once and lives for the
  whole package run (the loop body is inside the `async with Session:`
  block). This is what makes the per-email "next user message" model work
  and is why `pa-session` is dropped (§3.4).
- Agent definitions are markdown files with YAML frontmatter (`name`,
  `description`, `tools`, optional `model`). Built-in tools may be referenced
  with or without the `yoker:` prefix and are matched case-insensitively;
  plugin tools must use their full namespace (e.g. `pkgq:find`).
- Tools are plain Python functions/callables annotated with guardrail markers
  (`Path`, `Url`, `Query`, `Text`). Plugins expose tools, skills, and agents
  via a top-level `__YOKER_MANIFEST__`.
- Skills are loaded from configured `skills/` directories and invoked via the
  `yoker:skill` tool or `agent.inject_skill_context(name, args)`.
- The whole project hinges on this seam. It is usable today (yoker 0.8.0,
  released 2026-07-15): `Agent` + `agent_definition` + `process` is sufficient.
  No blocker. The plugin API (`PluginManifest`, `__YOKER_MANIFEST__`,
  `load_plugins`) is functional with one published third-party consumer
  (`pkgq`); still 0.x so breaking changes are possible, but the contract
  is simple (a dataclass plus a module attribute), so stability risk is
  low.

### 2.3.1 Dual-mode architecture (consumer + provider + reusable plugin)

`yoker-assistant` is BOTH a standalone yoker SDK consumer AND a yoker
plugin provider. This is the design-intended pattern — yoker itself is
dual-mode. The clean code shape:

- Define the `md_to_html` tool in `src/yoker_assistant/tools.py` as a
  plain Python function with yoker tool annotations
  (`Annotated[str, Text(...)]`).
- Expose `__YOKER_MANIFEST__ = PluginManifest(tools=[md_to_html],
  agents_dir="agents")` in `src/yoker_assistant/__init__.py`. The
  `agents_dir` field tells the yoker plugin loader to discover
  `agents/*.md` inside the installed `yoker_assistant` package — so
  external yoker consumers can reference the assistant agent by name
  (`yoker_assistant:assistant`) from their `Session`'s registry. The
  `__init__.py` must ONLY define the manifest and import tool functions
  — NO `Agent` construction or loop logic there (that lives in
  `__main__`/`loop`/`agent` modules). This discipline avoids any
  circular import.
- The user adds the plugin registration to their `~/.yoker.toml`:
  `[plugins] enabled = true; packages = ["yoker_assistant", "pkgq"]`
  and `[plugins.trusted] yoker_assistant = true; pkgq = true`.
  Self-trust is REQUIRED for unattended operation: with no TTY to
  prompt, the trust gate rejects untrusted plugins in non-interactive
  mode. The package documents this requirement (and ships a
  `yoker.toml.example` as reference documentation). Self-registration
  via a repo-level `yoker.toml` does NOT work for the primary `uvx`
  deployment model: yoker resolves project config from the current
  working directory (`./yoker.toml`) and the user's home
  (`~/.yoker.toml`), NOT from the package install location — so when
  run via `uvx yoker-assistant`, a `yoker.toml` inside the installed
  package is never read. A repo-level `yoker.toml` is only read during
  local dev (when the cwd is the checkout) and there it clobbers the
  user's backend/model config. The user's `~/.yoker.toml` is the
  correct location for plugin registration.
- The `Agent` is resolved by name (`yoker_assistant:assistant`) from the
  `Session`'s `AgentRegistry`, which the plugin loader populates from the
  installed package's `agents/` directory (declared via
  `agents_dir="agents"` in `__YOKER_MANIFEST__`). No manual definition
  loader, no relative filesystem path that would break when the package is
  installed. Plugins load from `~/.yoker.toml` automatically. No
  `plugins=()` arg is needed.
- External consumers load yoker-assistant's tools the IDENTICAL way:
  `pip install yoker-assistant` plus the same `[plugins]` /
  `[plugins.trusted]` lines in their `~/.yoker.toml`. Self-consumption
  and third-party consumption use the same mechanism — this is the
  elegant showcase point.
- The agent definition's `tools:` frontmatter declares
  `yoker_assistant:md_to_html` (full namespace for a plugin tool),
  which resolves to the tool registered by the plugin loader.

This adds a THIRD layer to the demo: (1) consumer of yoker's built-in
curated tools, (2) provider of its own named safe tool, (3) reusable —
any yoker consumer can load the tool. Minimal cost: one manifest
declaration plus three lines in the user's `~/.yoker.toml`.

### 2.4 The simple-email-gw seam

`simple-email-gw` provides both async and sync clients. Because yoker is
async-native, the natural choice is the **async** API for the loop, but the
sync wrappers (`SyncIMAPClient`, `SyncSMTPClient`) exist for simpler
synchronous code. The async API (confirmed from `simple_email_gw/__init__.py`
and the client sources):

```python
from simple_email_gw import get_pool

# The pool reads EMAIL_* env vars via ServerConfig and caches clients.
# The loop only knows the account name ("default" — the SDK convention).
pool = await get_pool()
imap = await pool.get_imap_client("default")
smtp = await pool.get_smtp_client("default")

# simple_email_gw 0.3.0 IMAPClient/SMTPClient do NOT implement
# __aenter__/__aexit__; they expose explicit connect()/disconnect() methods.
# The loop (P2-005) calls them directly: `await connect()` + `await
# disconnect()` bookend EACH iteration. The poll interval is several
# minutes, so holding an idle connection open across the sleep would just
# time out server-side every time — reconnecting per iteration is simpler
# and avoids the reconnect-on-failure guard entirely. The first
# iteration's connect is the credential check (no startup fast-fail
# connect outside the loop). No wrapper class, no indirection layer —
# the loop owns the gateway lifecycle explicitly. The pool returns
# cached but NOT-yet-connected clients, so the explicit connect() is
# still required.
while not stop.is_set():
    await imap.connect()
    try:
        ids = await imap.search(folder="INBOX", criteria="UNSEEN")
        msg = await imap.fetch_message(message_id=ids[0], folder="INBOX")
        # msg -> dict with id, folder, subject, from, to, body, attachments
        await imap.mark_message(message_id, "INBOX", "\\Seen", "add")
        await imap.move_message(message_id, "INBOX", "Archive")
    finally:
        await imap.disconnect()

# SMTPClient is fire-and-forget per send (no connect()/disconnect()).
await smtp.reply_email(to=[sender], subject=f"Re: {subject}",
                       html_body=reply_html, in_reply_to=msg_id)
```

**Errata (P1-003 cross-domain review):** an earlier version of this section
showed `async with IMAPClient(account) as imap:`. That is inaccurate —
simple_email_gw 0.3.0 `IMAPClient`/`SMTPClient` are NOT async context
managers; they expose explicit `connect()`/`disconnect()` methods. The loop
calls those methods directly (construct once via the pool, then per
iteration `await imap.connect()` ... `await imap.disconnect()` in a
`finally`). There is NO `Mailbox` wrapper class and no seam object with
`__aenter__`/`__aexit__` or `connect()`/`close()` methods — an earlier
design proposed one, but it was descoped per owner feedback (wrapping two
existing classes in a third class added no benefit for a demo/tutorial).
The method signatures and behaviour described below remain correct.

**Connection lifetime (PR #7 round-2 owner feedback):** the loop does NOT
hold the IMAP connection open across the multi-minute poll interval. Each
iteration bookends with `connect()` / `disconnect()`. A dropped
connection mid-iteration surfaces as a per-message exception (logged,
message left UNSEEN, retried next iteration with a fresh connection); no
reconnect-on-failure guard is needed. This simplifies the loop and matches
the owner's observation that an idle connection would time out every time.

`EmailAccount` fields: `name`, `imap_host`, `smtp_host`, `username`,
`password`. Configuration is read by the SDK's `ServerConfig` from env vars
(`EMAIL_IMAP_HOST`, `EMAIL_SMTP_HOST`, `EMAIL_USERNAME`, `EMAIL_PASSWORD`)
or a multi-account JSON (`EMAIL_ACCOUNTS_JSON`). The loop does not parse
these — it passes the literal account name `"default"` to the pool.

**Seam decision (confirmed):** async `IMAPClient`/`SMTPClient` obtained from
`ConnectionPool` and called directly from yoker's async loop. This avoids
running two event loops (yoker's + the sync wrapper's background thread),
delegates account/env-var parsing to the SDK, and is the clean fit for an
async-native SDK.

## 3. The c3 → yoker-assistant Porting Map

The adaptation principle (STANDARDS.md "c3 to yoker adaptation"): keep the
concepts — what an agent is, what a skill is — and rework the mechanics for
the yoker context. c3 runs inside Claude Code with its own orchestrator;
yoker is an SDK/runtime with different mechanics. For each adapted piece,
what is kept verbatim and what is reworked is stated explicitly.

### 3.1 The agent definition (`src/yoker_assistant/agents/assistant.md`)

The agent definition is **packaged inside the yoker_assistant package**
(`src/yoker_assistant/agents/assistant.md`) and discovered at runtime by
yoker's plugin loader via the manifest's `agents_dir="agents"` field. This
fixes the relative-path fragility the owner flagged in PR #7 round 2
("a file path won't work when the assistant is run from a package"). The
loop constructs a `Session` and sets `config.agent =
"yoker_assistant:assistant"`, so Session resolves the assistant by name
from the plugin-loaded `AgentRegistry` — no manual definition loader in
the loop. External yoker consumers reference the agent the same way
(`yoker_assistant:assistant`) via their own `Session`'s registry. The
`agent` tool is injected by Session (gated by
`config.tools.agent.enabled`, default True); populating the assistant's
`agents:` allowlist in `assistant.md` is a separate follow-up so the
tool can actually spawn sub-agents.

| Element | c3 original | yoker-assistant | Verdict |
|---|---|---|---|
| Concept: a personal assistant that organizes unstructured input into actions, tracks progress, replies | Yes | Yes | **KEPT** |
| Markdown + YAML frontmatter format | Yes | Yes (yoker agent definition format) | **KEPT** |
| `name`, `description`, `tools`, `color` frontmatter | Yes | Yes (yoker accepts `name`, `description`, `tools`, optional `model`) | **KEPT** (drop `color`, a Claude Code UI hint) |
| Reading `PERSONAL.md` first to establish identity | Yes | Yes, via `yoker:read` | **KEPT** (read AND write: the agent may add learned behaviours to `PERSONAL.md` for later, via `yoker:update`/`yoker:write`) |
| Workflow phases (Initialize → Process → Reply → Update) | Yes | Yes, conceptually | **KEPT** (rewritten to fit the email handoff) |
| Email Operations section (MCP tool ordering, mark-read/archive) | Yes | Removed from agent; done by Python | **REMOVED** |
| Guardrail "Use MCP tools for email — never access servers directly" | Yes | Removed; agent has no email tools at all | **REMOVED** |
| Skill priority table (git-activity-report, project-status, commit via c3: skills) | Yes | Adapted: these skills do not exist in yoker-assistant's scope | **REWORKED** (drop c3-specific skill references) |
| Memory / PERSONAL.md personalization sections | Yes | Yes | **KEPT** (mechanics reworked to yoker file tools) |

### 3.2 The tools list (frontmatter `tools:`)

The c3 assistant declares:

- Base read access: `Read`, `Glob`, `Grep`, `Skill`
- Write access: `Write`, `Edit`
- Online: `WebSearch`, `WebFetch`
- Execution: `Bash`
- Interaction: `AskUserQuestion`, `PushNotification`
- MCP support: `ListMcpResourcesTool`, `ReadMcpResourceTool`
- MCP Email Tools: `mcp__plugin_c3_email__*` (10 tools)
- MCP PacKaGe Query: `mcp__plugin_c3_pkgq__find_package`
- Sub-agents: `Agent`

Porting verdicts per tool (yoker built-ins are namespaced `yoker:` and matched
case-insensitively to bare names):

| c3 tool | yoker-assistant mapping | Verdict | Rationale |
|---|---|---|---|
| `Read` | `yoker:read` | **KEPT** | Core file reading; yoker built-in with `PathGuardrail`. |
| `Glob` | `yoker:list` | **REWORKED** | yoker has `list` (directory listing with pattern/depth), not a separate `Glob`. Map glob-style listing to `yoker:list`. |
| `Grep` | `yoker:search` | **REWORKED** | yoker has `search` (regex/glob content search) with complexity limits. |
| `Skill` | `yoker:skill` | **KEPT** | yoker registers a `skill` tool when skills are loaded. |
| `Write` | `yoker:write` | **KEPT** | Built-in with overwrite protection. |
| `Edit` | `yoker:update` | **KEPT** | yoker's edit tool is `update` (replace/insert/delete with diffs). |
| `WebSearch` | `yoker:websearch` | **KEPT** | Built-in with SSRF/rate-limit guardrails. |
| `WebFetch` | `yoker:webfetch` | **KEPT** | Built-in with URL validation. |
| `Bash` | — | **REMOVED** | yoker's safety model: agents get a curated set of safe, named tools, never an open shell. This is part of what the showcase demonstrates. Replaced by the curated yoker tools above. |
| `AskUserQuestion` | — | **REMOVED** | A Claude Code interactive UI concept. There is no interactive UI; the only channel is email. Clarifications go into the reply text. |
| `PushNotification` | — | **REMOVED** | Claude Code UI concept; no equivalent in unattended email mode. |
| `ListMcpResourcesTool` | — | **REMOVED** | MCP-specific; not part of yoker's tool model for this showcase. |
| `ReadMcpResourceTool` | — | **REMOVED** | MCP-specific. |
| `mcp__plugin_c3_email__*` (all 10) | — | **REMOVED** | The email loop moves to Python. This is the central reason the project exists. |
| `mcp__plugin_c3_pkgq__find_package` | `pkgq:find` | **REWORKED** | Loaded as a yoker **plugin** (via `yoker.toml [plugins]` / `--with pkgq`) instead of an MCP server. Same capability, yoker-native mechanics. |
| `Agent` | `yoker:agent` | **KEPT** | yoker spawns isolated subagents with recursion limits; matches c3's "1 level of sub-agents" intent. |

### 3.3 The bounded tool set for this first pass

After the port, the assistant's curated tool set is:

- `yoker:read`, `yoker:list`, `yoker:search` — read access
- `yoker:write`, `yoker:update` — write access
- `yoker:websearch`, `yoker:webfetch` — online access
- `yoker:skill` — invoke the ported skills
- `yoker:agent` — bounded subagent spawning (1 level)
- `yoker:git` — **full git** (read + commit + push). This is part of the
  showcase: the agent autonomously maintains its own `PERSONAL.md`
  learned-behaviours file in version control via bounded git tools, not a
  shell. See the demo beat in §4.3.
- `pkgq:find` — via the pkgq plugin (demonstrates yoker plugin
  loading)
- `yoker_assistant:md_to_html` — a **custom local tool** defined in THIS
  package as a yoker plugin (see §2.3.1). Defined in
  `src/yoker_assistant/tools.py`, exposed via `__YOKER_MANIFEST__` in
  `src/yoker_assistant/__init__.py`, and registered via the user's
  `~/.yoker.toml [plugins]` (NOT programmatic). Converts the agent's markdown
  reply to HTML for email rendering. This is the showcase's "create your
  own bounded tool" example and pairs with the built-in curated tools above
  to demonstrate both halves of yoker's tool model: using yoker's built-ins
  AND authoring your own named, safe, locally-defined tool — and, because
  it is plugin-registered, any external yoker consumer can load it the same
  way.

This set is deliberately small. It demonstrates yoker's safety model:
named, guardrailed tools, no open shell — and it shows both modes of tool
authorship (consume built-ins, define your own).

### 3.4 The skills

The c3 assistant invokes (via the `Skill` tool): `pa-inbox`, `pa-session`,
`pa-outbox`, and the email-driven variant `pa-email`. Each is a c3 skill
(`../c3/skills/<name>/SKILL.md`).

#### pa-email — REMOVED

`pa-email` is the email inbox processor: search `UNSEEN`, read each message,
categorize, take actions, reply, mark read, archive. **This entire skill is
removed from the agent.** Its responsibilities move to Python:

| pa-email responsibility | New home | Verdict |
|---|---|---|
| Search `UNSEEN` in INBOX | Python loop (IMAP search) | **MOVED to Python** |
| Read each message | Python fetch | **MOVED to Python** |
| Categorize content (actionable/clarification/cross-cutting/info) | The agent (reasoning) | **MOVED to agent** (it is reasoning, not structured work) |
| Execute actions (update TODOs, create memory) | The agent via its tools | **KEPT in agent** |
| Compose reply body | The agent | **KEPT in agent** |
| Send reply email | Python (SMTP) | **MOVED to Python** |
| Mark read + archive | Python (IMAP) | **MOVED to Python** |
| Loop interval (`/loop 30m /pa-email`) | Python poll interval | **MOVED to Python** |

#### pa-inbox — REWORKED

`pa-inbox` processes unstructured input from files in an `inbox/` directory,
categorizes items, executes actions, generates an outbox reply, and archives
files. In yoker-assistant the "inbox" is the email itself, delivered by
Python.

| pa-inbox element | Verdict | Notes |
|---|---|---|
| Concept: take unstructured input, categorize, act, reply | **KEPT** | The agent's core reasoning job. |
| Item categorization rules (actionable / needs clarification / cross-cutting / information / reply-to-previous) | **KEPT** | Pure reasoning; reusable verbatim. |
| Project detection, clarity indicators | **KEPT** | Reasoning. |
| File I/O: list `inbox/`, move to `inbox/archive/`, write `outbox/` files | **REMOVED** | Python handles mail transport; the agent does not manage an inbox directory. The reply is the agent's text output, not an outbox file. |
| `re-` threaded reply naming | **REMOVED** | Email threading (In-Reply-To/References) replaces it. |
| Memory integration (create memory files) | **KEPT** | Via `yoker:write`; memory lives under a configured memory dir. |
| Step "Update session state" | **DROPPED** | yoker's persistent context manager carries session state; no skill step needed (see pa-session). |

The reworked `pa-inbox` becomes a reasoning skill: given an email's content
(as handed off by Python), categorize each item, take actions with the
agent's tools, and produce the reply (markdown, converted to HTML via the
`md_to_html` tool). It no longer touches the mailbox or the filesystem
inbox/outbox.

#### pa-outbox — REWORKED

`pa-outbox` generates formatted reply files in an `outbox/` directory and
archives originals.

| pa-outbox element | Verdict | Notes |
|---|---|---|
| Reply format (Actions Taken table, Memory Created, Status, Pending Questions) | **KEPT** | The reply body the agent produces (in markdown, then converted to HTML via the `md_to_html` tool); Python emails the HTML verbatim. |
| Clarification vs resolution reply types | **KEPT** | Reasoning; decides reply content. |
| Writing reply files to `outbox/` | **REMOVED** | The reply is `Agent.process()` return value (HTML); Python emails it. |
| Archive management (move originals) | **REMOVED** | Python archives the email. |
| Markdown-to-HTML conversion for email | **REWORKED** | RESOLVED: the agent converts its markdown reply to HTML via the custom `yoker_assistant:md_to_html` tool (a yoker plugin/tool defined in this package); Python emails the HTML verbatim. Not a Python-side conversion, not plain text. |

#### pa-session — DROPPED

`pa-session` maintains `session-state.md` for continuity across iterations.

**Decision: drop `pa-session` entirely.** The architecture uses one
long-lived agentic session with a **persistent context manager**
(§2.1/§2.3). yoker's context manager carries session state natively across
`process()` calls — the agent remembers the running conversation across
emails without an external state file. On top of that, the agent writes
memory files and `PERSONAL.md` learned behaviours (the latter committed via
`yoker:git`). There is no job left for `pa-session` to do that the context
manager does not already cover, so keeping it would be dead surface area and
would violate "ultra clean". Dropped; documented here.

### 3.5 Summary of the porting map at a high level

- **KEPT**: the assistant concept and identity; the agent definition format;
  the core reasoning workflow (categorize → act → reply); item categorization
  rules; memory creation; the reply format; the curated read/write/web/skill/
  agent tool set.
- **REMOVED**: all MCP email tools; the `pa-email` skill; `Bash`; Claude Code
  UI tools (`AskUserQuestion`, `PushNotification`, MCP resource tools); file
  inbox/outbox/archive I/O from skills; the `color` frontmatter field.
- **REWORKED**: `Glob`→`yoker:list`, `Grep`→`yoker:search`, `Edit`→`yoker:update`;
  the pkgq tool from MCP to a yoker plugin; `pa-inbox`/`pa-outbox` from
  file-based to email-handoff-based reasoning skills.
- **DROPPED**: `pa-session` — yoker's persistent context manager carries
  session state natively; no external state file needed.
- **ADDED**: a custom local `md_to_html` tool (yoker plugin/tool defined in
  this package) — the showcase's "create your own bounded tool" example.

## 4. The Handoff Contract

This is the most important seam in the project. It defines exactly what
Python hands to the agent and what the agent returns.

### 4.1 What Python hands to the agent

The package runs **one long-lived agentic session**. The agent's identity,
workflow, categorization rules, and guardrails live in the agent definition
(`src/yoker_assistant/agents/assistant.md`, packaged inside this package and
loaded by yoker as the system prompt) — NOT in the
per-email payload. At **startup** (one-time session-setup step), the package
constructs the `Agent` once with a persistent context manager and sends a
ONE-TIME initialize message to the session before the loop begins (an
explicit startup step). The agent definition instructs the agent to read
`PERSONAL.md` (via `yoker:read`) on that first turn and initialize its
identity for the ongoing session. After that, each incoming email is the
next user message in the SAME session. This setup is not repeated per
email. (If the owner later wants it purely definition-driven with no
startup message, that is a minor change — but for now the explicit
initialize message is the design.)

Each incoming email is then delivered to that SAME session as the **next
user message** via `agent.process(message)`. The message is a single string
(yoker's `process(message: str)`) carrying only the email itself — no
instructions block:

```
From: <sender name> <sender@email>
Subject: <original subject>
Date: <rfc date>

<body of the email, as plain text>
```

The agent REMEMBERS the running conversation across emails: continuity lives
in the persistent session (yoker's context manager) plus memory files and
`PERSONAL.md` learned behaviours the agent writes (and commits via
`yoker:git`). No per-email instructions block is sent. If a one-time
session-setup instruction is needed at startup, it is described separately
in the session-setup step above — not repeated in each email payload.

### 4.2 What the agent returns

The agent composes its reply in markdown, then calls the custom
`yoker_assistant:md_to_html` tool to convert it to HTML. `Agent.process()`
returns that HTML string. That string **is** the reply body. Python does not
interpret it or re-render it; it sends the HTML verbatim as the email body
(subject `Re: <original subject>`, to the sender). Markdown and email do not
render well together, so the reply is HTML end-to-end.

### 4.2.1 Conversation-style logging

Per owner feedback (PR #7 round 2), `_process_one` emits two `logger.info`
calls framing the conversation between user and agent — one before
`agent.process` (the incoming handoff, "user turn") and one after (the
agent's reply, "agent turn"), with `===` separators so the two turns are
visible in normal INFO-level log output. An empty reply is logged
explicitly as `"(empty — no reply)"` so a silent agent turn still shows up
in the conversation log. The one-time `Initialize` setup turn is NOT
logged — it is a session-setup handshake, not an incoming message.

### 4.3 How Python turns that into a reply

1. Capture `reply_html = await agent.process(message)` (the agent has
   already converted markdown → HTML via its tool).
2. Four-way branch on `reply_html`:
   - **`{{NO_REPLY}}` sentinel present** (intentional silence): mark the
     original `\Seen` and archive it. No reply is sent.
   - **empty/whitespace reply** (transient problem): leave the message
     `UNSEEN` so it is retried next iteration. No mark, no archive, no send.
   - **unsafe HTML** (guard failure — `<script>`/`<style>`/`<img>`/
     `<iframe>`/`<object>`/`<embed>`/`<form>` or `on*=` event handlers):
     mark the original `\Seen` (do NOT archive — the owner controls
     reprocessing by removing `\Seen`), and send a plain-text notice to the
     original sender via `reply_email(to=sender, body=notice, ...)`.
   - **valid HTML reply**: send via
     `SMTPClient.reply_email(to=sender, subject=f"Re: {subject}", body="",
     html_body=reply_html, in_reply_to=message_id)` (threading preserved),
     then mark `\Seen` and archive.
3. Every send is a reply — always `reply_email`; there is NO `send_email`
   fallback. `to` is a bare address string extracted via
   `parseaddr(msg["from"])[1]` (the gateway's `validate_email` rejects
   display-name headers). `body=""` is required by `reply_email`'s
   signature; the plain-text alternative is intentionally empty in the
   first pass (accessibility polish deferred).
4. **Ordering (send → mark read → archive)** for the valid-reply branch:
   send the reply before marking read so a send failure leaves the message
   `UNSEEN` for retry. Mark read immediately after a successful send, then
   archive.

**Demo beat (the visible "acts on behalf of the owner" moment):** the agent
learns a behaviour from an email → writes it to `PERSONAL.md` (via
`yoker:update`) → commits and pushes via `yoker:git` (full git, not a shell).
This is the showcase's headline demonstration of bounded tools acting on the
owner's behalf: the assistant autonomously maintains its own
learned-behaviours file in version control.

### 4.4 Ordering and idempotency

- Process one email per loop iteration (simplest, safest for a showcase).
  Batching is a later optimization, out of scope.
- Idempotency relies on IMAP flags, exactly as `pa-email` did: `UNSEEN`
  search returns only unprocessed messages; mark-read + archive ensures a
  message never reappears. No deduplication state is needed.
- **The ordering (send → mark read → archive) is owned by the loop module
  (P2-005).** There is no `Mailbox` seam object that owns it; the loop
  sequences the calls to `IMAPClient`/`SMTPClient` directly.
- **Critical ordering:** send the reply **before** marking read/archiving. If
  the reply fails, do not mark read — the message stays `UNSEEN` and is
  retried next iteration. If the reply succeeds but mark/archive fails, the
  message is still `UNSEEN`; next iteration it will be reprocessed and a
  duplicate reply sent. To avoid duplicates on this partial-failure path,
  Python should mark read **immediately after** a successful send, before
  archiving. A marked-read-but-not-archived message is excluded from `UNSEEN`,
  so it will not be reprocessed; it just lingers in INBOX until the next loop
  tidies it. This is acceptable and documented.

## 5. Configuration Model

Three configuration concerns, kept separate (no bleeding):

### 5.1 Email account (`simple-email-gw`)

- The loop does NOT parse `EMAIL_*` env vars itself. It obtains IMAP/SMTP
  clients from the SDK's ``ConnectionPool`` via the literal account name
  ``"default"`` (the SDK's ``ServerConfig.account_name`` default):
  ```python
  pool = await get_pool()
  imap = await pool.get_imap_client("default")
  smtp = await pool.get_smtp_client("default")
  await imap.connect()  # pool returns cached-but-unconnected clients
  ```
- ``EmailAccount`` fields (`name`, `imap_host`, `smtp_host`, `username`,
  `password`) and their env-var sources (`EMAIL_IMAP_HOST`, `EMAIL_SMTP_HOST`,
  `EMAIL_USERNAME`, `EMAIL_PASSWORD`, or `EMAIL_ACCOUNTS_JSON` for multi-account)
  are read inside the SDK's ``ServerConfig`` — yoker-assistant's only account
  knowledge is the name ``"default"``.
- IMAP connection lifetime: held active for the loop's lifetime (one
  ``connect()`` at startup for fast-fail on bad credentials, one
  ``disconnect()`` in the ``finally`` block). A reconnect-on-failure guard
  wraps ``imap.search`` so a dropped idle connection (after the 60s sleep)
  triggers one ``disconnect()`` + ``connect()`` + retry rather than killing
  the loop.
- Loop parameters: `poll_interval` (seconds, default 60), `archive_folder`
  (default `Archive`), `inbox_folder` (default `INBOX`).

### 5.2 yoker (`~/.yoker.toml`)

The backend, model, and permissions live in the user's `~/.yoker.toml`,
created by yoker's bootstrap. The `[plugins]` / `[plugins.trusted]` lines
also live there — that is the correct location for plugin registration
because yoker resolves project config from `~/.yoker.toml` (user) and
`./yoker.toml` (cwd), NOT from the package install location. A repo-level
`yoker.toml` is only read during local dev (when the cwd is the checkout)
and would clobber the user's backend config there. The package provides a
`yoker.toml.example` as documentation only — reference for the lines the
user must add to their `~/.yoker.toml`, not a checked-in active config.

- Backend + model (provider, base_url, api_key, model, parameters).
- Permissions (`filesystem_paths`, `network_access`, tool enablement).
- Plugins: `[plugins] enabled = true; packages = ["yoker_assistant", "pkgq"]`
  and `[plugins.trusted] yoker_assistant = true; pkgq = true` (self-trust
  required for unattended operation).
- Skills directory (`skills.directories = ["./skills"]`).
- Agents directory (optional; the agent is loaded by explicit path).

### 5.3 Assistant / personalization

- `agent_definition` (the ported assistant agent definition, loaded from
  the package's `agents/assistant.md` via `find_package_subdirectory` +
  `load_agent_definitions`).
- `PERSONAL.md` path (owner identity, tone, goals). The agent reads it at
  session startup via `yoker:read` and may write to it (learned behaviours)
  via `yoker:update`/`yoker:write`; the agent also commits and pushes it via
  `yoker:git`.
- Recipient safety: reply only to the configured owner address. This is a
  **configuration option of `simple-email-gw`** (`EMAIL_RECIPIENT_ADDRESSES`
  whitelist) — not package-level code. Python relies on `simple-email-gw`'s
  existing config; no package-level allowlist code is written. This is the
  email-side safety boundary and it lives in the gateway, not in this
  package.

## 6. Entry Point

The package is started as a module / console script:

```
python -m yoker_assistant
# or, after install:
yoker-assistant
```

It runs `asyncio.run(main())`, which constructs the `EmailAccount`, the
`Agent(agent_definition=..., context_manager=<persistent>)` **once**, runs the
one-time session-setup step (agent reads `PERSONAL.md` and initializes), and
enters the loop. A `--once` flag processes a single iteration and exits
(useful for tests and demos). Graceful shutdown on `SIGINT`/`SIGTERM`: finish
the current message, close IMAP/SMTP connections, exit.

## 7. Loop Behavior

- **Poll interval:** configurable, default 60s. Documented, not hardcoded in
  hot paths.
- **No email:** log at INFO (or silently), sleep, repeat. Never error on an
  empty inbox.
- **Per-message flow:** fetch → handoff → reply → mark read → archive, with
  the ordering in §4.4.
- **Error handling:**
  - IMAP/SMTP connection failure: log, back off (e.g. double the interval up
    to a cap), retry. Do not crash the loop.
  - Agent `process` failure (e.g. backend network error): log, do **not**
    mark read, continue to next message or next iteration. The message
    retries on the next `UNSEEN` search.
  - Reply send failure: do not mark read; retry next iteration.
  - Guard failure (unsafe HTML in agent output): mark `\Seen` (no archive)
    and send a plain-text notice to the original sender. The owner controls
    reprocessing by removing `\Seen`.
  - Empty/whitespace reply (transient): leave `UNSEEN`, no mark/archive,
    retry next iteration. The `{{NO_REPLY}}` sentinel is the agent's
    intentional-silence signal and is handled separately (mark + archive).
  - Unexpected exception per message: log, skip the message (leave it
    `UNSEEN` so it is retried), continue the loop.
  - **C1 startup guard:** the loop refuses to start when the recipient
    whitelist is disabled — the whitelist fails open, so an unset whitelist
    would let the assistant reply to arbitrary senders. `run()` raises
    `RuntimeError` (citing `EMAIL_RECIPIENT_DOMAINS`,
    `EMAIL_RECIPIENT_ADDRESSES`, or `EMAIL_RECIPIENT_WHITELIST_JSON`) before
    constructing the `Agent`.
- **Graceful shutdown:** on signal, stop accepting new messages, finish the
  in-flight message, close connections, exit 0.
- **No background concurrency in the first pass:** one loop, one message at a
  time. Simple and demonstrable.

## 8. Resolved Questions

All design questions are resolved by the owner's decisions. No item below
still needs owner confirmation.

1. **Personalization (`PERSONAL.md`) delivery.** RESOLVED: the agent reads
   `PERSONAL.md` at session startup via `yoker:read` (the definition instructs
   this, as c3 does today) AND the agent may WRITE to `PERSONAL.md` (adding
   learned behaviours for later). This read/write behaviour is KEPT AS-IS from
   c3 for the first pass. No change.

2. **async vs sync email clients.** RESOLVED: async `IMAPClient`/`SMTPClient`
   inside yoker's async loop.

3. **Agent context: fresh per email vs persistent.** RESOLVED: PERSISTENT —
   one long-lived session. The `Agent` is constructed ONCE at startup with a
   persistent context manager; each email is the next user message in that
   session. The agent remembers the running conversation across emails.
   Continuity lives in the session plus memory files and `PERSONAL.md`.

4. **`yoker:git` tool.** RESOLVED: FULL git (read + commit + push), not
   read-only. The agent updates `PERSONAL.md`, commits, and pushes to its
   repository — the demo beat in §4.3.

5. **Reply format: plain text (markdown) vs HTML.** RESOLVED: HTML, not plain
   text. The agent uses a custom local `md_to_html` tool (a yoker plugin/tool
   defined in this package) to convert its markdown reply to HTML; Python
   emails the HTML verbatim. Markdown and email do not render well together.

6. **Attachments.** Out of scope for the first pass (do not fetch or process
   attachments). The `fetch_message` result includes attachment metadata but
   Python ignores it. Flagged in docs.

7. **Recipient safety / who the assistant replies to.** RESOLVED: this is a
   configuration option of `simple-email-gw` (`EMAIL_RECIPIENT_ADDRESSES`).
   No package-level allowlist code is written; Python relies on the
   gateway's existing config. Single owner address is the model.

8. **Model backend availability.** yoker needs a configured backend (Ollama
   running locally, or an API key for a cloud provider). This is a deployment
   prerequisite, documented in the tutorial, not a code concern. Not a blocker
   for the analysis.

9. **`color` frontmatter field and Claude Code-only fields.** Dropped. No
   other c3-specific frontmatter is load-bearing.

10. **Skill porting fidelity.** The reworked `pa-inbox`/`pa-outbox` carry
    substantial prose from c3. Per STANDARDS.md "ultra clean", the ported
    skills should be trimmed to what the yoker-assistant agent actually does.
    The task is to port and slim, not copy verbatim: port the reasoning rules
    verbatim where they still apply; rewrite all file/mailbox mechanics
    sections.

11. **Context-window growth (compaction/summarization/trimming).** RESOLVED:
    this is yoker's responsibility, not this package's. The package uses
    yoker's persistent context manager and trusts yoker to handle
    context-window growth. It is out-of-scope by design because it is
    yoker's job — NOT a known limitation of yoker-assistant. The analysis
    records no "known limitation" framing for context management; the
    package relies on yoker for it.

12. **Dual-mode / plugin registration.** RESOLVED: yoker-assistant is
    dual-mode — both a yoker SDK consumer and a yoker plugin provider.
    The package exposes `__YOKER_MANIFEST__` in `src/yoker_assistant/__init__.py`
    (manifest only; no `Agent` construction there). Self-trust is configured
    in the user's global `~/.yoker.toml` (`[plugins] enabled = true;
    packages = ["yoker_assistant", "pkgq"]` and `[plugins.trusted]
    yoker_assistant = true; pkgq = true`, required for unattended
    operation) — NOT in a repo-level `yoker.toml`. yoker resolves project
    config from `cwd` and `~`, not the package install location, so a
    repo-level `yoker.toml` is only read during local dev and would
    clobber the user's backend config there. The package documents the
    required lines and ships a `yoker.toml.example` as reference. See
    §2.3.1 for the full pattern.

13. **Session-setup mechanism.** RESOLVED: one-time initialize message
    before the loop, plus definition-driven behaviour. The package sends an
    explicit startup message to the session so the agent reads `PERSONAL.md`
    and sets up on the first turn; subsequent emails are the next user
    messages. See §4.1.

### 8.1 Dual-mode showcase (one-paragraph summary)

`yoker-assistant` is simultaneously three layers of yoker's tool model in
one package: a **consumer** of yoker's built-in curated tools
(`yoker:read`, `yoker:git`, …), a **provider** of its own named safe tool
(`yoker_assistant:md_to_html`), and a **reusable plugin** that any external
yoker consumer can load with `pip install yoker-assistant` plus the same
two `[plugins]` / `[plugins.trusted]` lines in their `~/.yoker.toml`.
Self-consumption and third-party consumption use the identical mechanism.

## 9. Requirements Coverage (informal)

This first pass satisfies the project's stated scope: port the agent +
skills, remove MCP email logic, wrap in the Python email loop, demonstrate
yoker-as-SDK with a curated tool set, and demonstrate BOTH halves of yoker's
tool model — using built-in curated tools AND authoring a custom local tool
(the `md_to_html` converter). It does **not** cover: other new bounded tools
(Phase B), attachment handling, batch processing, or multi-account support.
Those are explicitly deferred.