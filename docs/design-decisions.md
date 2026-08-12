# Design Decisions

This page documents the engineering choices behind `yoker-assistant`: what
was kept from the original assistant concept, what was reworked for the
Yoker SDK context, what was removed, and what was added. The condensed
version is in the [Tutorial](tutorial.md) §6; this page is the full
per-element reference.

## The agent definition

The agent definition is packaged inside the `yoker_assistant` package
(`src/yoker_assistant/agents/assistant.md`) and discovered at runtime by
Yoker's plugin loader via the manifest's `agents_dir="agents"` field. The
loop constructs a `Session` and sets `config.agent =
"yoker_assistant:assistant"`, so Session resolves the assistant by name
from the plugin-loaded `AgentRegistry` — no manual definition loader in the
loop.

| Element | Decision | Notes |
|---|---|---|
| Concept: a personal assistant that organizes input into actions, tracks progress, replies | **KEPT** | Core identity unchanged |
| Markdown + YAML frontmatter format | **KEPT** | Yoker's agent definition format |
| `name`, `description`, `tools` frontmatter | **KEPT** | Yoker accepts these fields |
| `color` frontmatter field | **REMOVED** | UI hint with no meaning in unattended email mode |
| Optional `model` frontmatter field | **ADDED** | Yoker supports per-agent model override |
| Reading `PERSONAL.md` first to establish identity | **KEPT** | Via `yoker:read`; also writes learned behaviours via `yoker:update` |
| Workflow phases (Initialize → Process → Reply → Update) | **KEPT** | Rewritten to fit the email handoff |
| Email operations (server tool ordering, mark-read/archive) | **REMOVED** | Moved to Python — the agent has no email tools |
| Guardrail "use server tools for email" | **REMOVED** | Agent has no email tools at all |
| Skill references to project-management skills | **REWORKED** | These skills are not in scope for this showcase |
| Memory / PERSONAL.md personalization sections | **KEPT** | Mechanics reworked to Yoker file tools |

## The tools list

The agent's curated tool set is deliberately small — named, guardrailed
tools, no open shell. Here is how each tool maps:

| Tool in this package | Origin | Decision | Rationale |
|---|---|---|---|
| `yoker:read` | file reading | **KEPT** | Core file reading; Yoker built-in with path guardrails |
| `yoker:list` | directory listing | **REWORKED** | Yoker has `list` (directory listing with pattern/depth) |
| `yoker:search` | content search | **REWORKED** | Yoker has `search` (regex/glob content search) with complexity limits |
| `yoker:write` | file writing | **KEPT** | Built-in with overwrite protection |
| `yoker:update` | file editing | **KEPT** | Yoker's edit tool (replace/insert/delete with diffs) |
| `yoker:websearch` | web search | **KEPT** | Built-in with SSRF/rate-limit guardrails |
| `yoker:webfetch` | web fetch | **KEPT** | Built-in with URL validation |
| `yoker:skill` | skill invocation | **KEPT** | Yoker registers a `skill` tool when skills are loaded |
| `yoker:agent` | subagent spawning | **KEPT** | Yoker spawns isolated subagents with recursion limits |
| `yoker:git` | version control | **ADDED** | Full git (read, commit, push) — the demo beat |
| `pkgq:find` | package docs lookup | **REWORKED** | Loaded as a Yoker plugin instead of a server tool |
| `yoker_assistant:md_to_html` | markdown→HTML | **ADDED** | Custom tool defined in this package (§8 of Tutorial) |
| open shell | — | **REMOVED** | Yoker's safety model: no open shell, only named tools |
| interactive UI prompt | — | **REMOVED** | No interactive UI; clarifications go in reply text |
| push notifications | — | **REMOVED** | No equivalent in unattended email mode |
| email server tools | — | **REMOVED** | Email loop moved to Python |
| resource listing tools | — | **REMOVED** | Not part of Yoker's tool model |

## What moved to Python

The email loop is the central design decision. Everything that is
structured work — no reasoning required — moved from the agent to Python:

| Responsibility | New home | Decision |
|---|---|---|
| Search `UNSEEN` in INBOX | Python loop (IMAP search) | **MOVED to Python** |
| Fetch each message | Python (IMAP fetch) | **MOVED to Python** |
| Categorize content | The agent (reasoning) | **KEPT in agent** |
| Execute actions (update TODOs, create memory) | The agent via its tools | **KEPT in agent** |
| Compose reply body | The agent | **KEPT in agent** |
| Convert reply to HTML | The agent via `md_to_html` tool | **KEPT in agent** |
| Send reply email | Python (SMTP) | **MOVED to Python** |
| Mark read + archive | Python (IMAP) | **MOVED to Python** |
| Loop interval / sleep | Python poll interval | **MOVED to Python** |

## What was reworked

### Inbox processing

The earlier approach processed unstructured input from files in an
`inbox/` directory. In yoker-assistant the "inbox" is the email itself,
delivered by Python.

| Element | Decision | Notes |
|---|---|---|
| Concept: take unstructured input, categorize, act, reply | **KEPT** | The agent's core reasoning job |
| Item categorization rules | **KEPT** | Pure reasoning; reusable |
| Project detection, clarity indicators | **KEPT** | Reasoning |
| File I/O: list inbox, move to archive, write outbox files | **REMOVED** | Python handles mail transport |
| Threaded reply naming | **REMOVED** | Email threading (In-Reply-To) replaces it |
| Memory integration | **KEPT** | Via `yoker:write` |
| Session-state update step | **DROPPED** | Yoker's context manager carries session state |

### Reply formatting

The earlier approach wrote formatted reply files to an `outbox/` directory.

| Element | Decision | Notes |
|---|---|---|
| Reply format (Actions Taken, Memory Created, Status, Questions) | **KEPT** | Agent produces markdown, converts to HTML |
| Clarification vs resolution reply types | **KEPT** | Reasoning; decides reply content |
| Writing reply files to outbox | **REMOVED** | Reply is `agent.process()` return value; Python emails it |
| Archive management | **REMOVED** | Python archives the email |
| Markdown-to-HTML conversion | **REWORKED** | Agent converts via custom `md_to_html` tool; Python emails HTML |

## What was dropped

### Session-state management

**Decision: dropped entirely.** The architecture uses one long-lived
agentic session with a persistent context manager. Yoker's context manager
carries session state natively across `process()` calls — the agent
remembers the running conversation across emails without an external state
file. On top of that, the agent writes memory files and `PERSONAL.md`
learned behaviours (the latter committed via `yoker:git`). There is no job
left for a separate session-state mechanism; keeping it would be dead
surface area and would violate "ultra clean". Dropped and documented here.

## Summary

- **KEPT**: the assistant concept and identity; the agent definition format;
  the core reasoning workflow (categorize → act → reply); item
  categorization rules; memory creation; the reply format; the curated
  read/write/web/skill/agent tool set.
- **REMOVED**: all email server tools; the open shell; interactive UI
  tools; file inbox/outbox/archive I/O; the `color` frontmatter field.
- **REWORKED**: file listing → `yoker:list`; content search →
  `yoker:search`; file editing → `yoker:update`; package docs lookup →
  Yoker plugin; inbox/reply from file-based to email-handoff-based.
- **DROPPED**: session-state management — Yoker's persistent context
  manager carries session state natively; no external state file needed.
- **ADDED**: `yoker:git` (full git for the demo beat); a custom
  `yoker_assistant:md_to_html` tool — the showcase's "create your own
  bounded tool" example.
