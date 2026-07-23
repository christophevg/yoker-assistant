# Porting Map — c3 → yoker-assistant

The adaptation principle, stated once: keep the concepts — what an agent is,
what a skill is — and rework the mechanics for the yoker context. c3 runs
inside Claude Code with its own orchestrator; yoker is an SDK/runtime with
different mechanics. For each adapted piece, what is kept verbatim and what
is reworked is stated explicitly.

This page is the full per-element table. The condensed verdicts are in the
[Tutorial](tutorial.md) §6.

## The agent definition

The agent definition is packaged inside the `yoker_assistant` package
(`src/yoker_assistant/agents/assistant.md`) and discovered at runtime by
yoker's plugin loader via the manifest's `agents_dir="agents"` field. The
loop constructs a `Session` and sets `config.agent =
"yoker_assistant:assistant"`, so Session resolves the assistant by name
from the plugin-loaded `AgentRegistry` — no manual definition loader in the
loop.

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

## The tools list (frontmatter `tools:`)

The c3 assistant declares: `Read`, `Glob`, `Grep`, `Skill`, `Write`, `Edit`,
`WebSearch`, `WebFetch`, `Bash`, `AskUserQuestion`, `PushNotification`,
`ListMcpResourcesTool`, `ReadMcpResourceTool`, `mcp__plugin_c3_email__*`
(10 tools), `mcp__plugin_c3_pkgq__find_package`, `Agent`.

Porting verdicts per tool (yoker built-ins are namespaced `yoker:` and
matched case-insensitively to bare names):

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
| `mcp__plugin_c3_pkgq__find_package` | `pkgq:find` | **REWORKED** | Loaded as a yoker **plugin** (via `yoker.toml [plugins]`) instead of an MCP server. Same capability, yoker-native mechanics. The published `pkgq` yoker plugin exposes its package-finder tool as `pkgq:find`, NOT `pkgq:find_package` (the MCP-server tool surface). |
| `Agent` | `yoker:agent` | **KEPT** | yoker spawns isolated subagents with recursion limits; matches c3's "1 level of sub-agents" intent. |

## The skills

The c3 assistant invokes (via the `Skill` tool): `pa-inbox`, `pa-session`,
`pa-outbox`, and the email-driven variant `pa-email`.

### pa-email — REMOVED

`pa-email` is the email inbox processor: search `UNSEEN`, read each message,
categorize, take actions, reply, mark read, archive. This entire skill is
removed from the agent. Its responsibilities move to Python:

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

### pa-inbox — REWORKED

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

### pa-outbox — REWORKED

`pa-outbox` generates formatted reply files in an `outbox/` directory and
archives originals.

| pa-outbox element | Verdict | Notes |
|---|---|---|
| Reply format (Actions Taken table, Memory Created, Status, Pending Questions) | **KEPT** | The reply body the agent produces (in markdown, then converted to HTML via the `md_to_html` tool); Python emails the HTML verbatim. |
| Clarification vs resolution reply types | **KEPT** | Reasoning; decides reply content. |
| Writing reply files to `outbox/` | **REMOVED** | The reply is `Agent.process()` return value (HTML); Python emails it. |
| Archive management (move originals) | **REMOVED** | Python archives the email. |
| Markdown-to-HTML conversion for email | **REWORKED** | The agent converts its markdown reply to HTML via the custom `yoker_assistant:md_to_html` tool (a yoker plugin/tool defined in this package); Python emails the HTML verbatim. Not a Python-side conversion, not plain text. |

### pa-session — DROPPED

`pa-session` maintains `session-state.md` for continuity across iterations.

**Decision: drop `pa-session` entirely.** The architecture uses one
long-lived agentic session with a persistent context manager. yoker's
context manager carries session state natively across `process()` calls —
the agent remembers the running conversation across emails without an
external state file. On top of that, the agent writes memory files and
`PERSONAL.md` learned behaviours (the latter committed via `yoker:git`).
There is no job left for `pa-session` to do that the context manager does
not already cover, so keeping it would be dead surface area and would
violate "ultra clean". Dropped; documented here.

## Summary at a high level

- **KEPT**: the assistant concept and identity; the agent definition format;
  the core reasoning workflow (categorize → act → reply); item
  categorization rules; memory creation; the reply format; the curated
  read/write/web/skill/agent tool set.
- **REMOVED**: all MCP email tools; the `pa-email` skill; `Bash`; Claude
  Code UI tools (`AskUserQuestion`, `PushNotification`, MCP resource
  tools); file inbox/outbox/archive I/O from skills; the `color`
  frontmatter field.
- **REWORKED**: `Glob`→`yoker:list`, `Grep`→`yoker:search`,
  `Edit`→`yoker:update`; the pkgq tool from MCP to a yoker plugin;
  `pa-inbox`/`pa-outbox` from file-based to email-handoff-based reasoning
  skills.
- **DROPPED**: `pa-session` — yoker's persistent context manager carries
  session state natively; no external state file needed.
- **ADDED**: a custom local `md_to_html` tool (yoker plugin/tool defined
  in this package) — the showcase's "create your own bounded tool" example.