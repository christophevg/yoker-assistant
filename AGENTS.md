# yoker-assistant Agent Guide

Essential context for working on the yoker-assistant codebase. For
user-facing documentation, see [README.md](README.md). For shared quality
standards across both showcase packages, see [STANDARDS.md](STANDARDS.md).

## Positioning

This is a **yoker-as-SDK** showcase: Python owns the email loop and calls
yoker as a library for the reasoning half. It is also a yoker plugin
provider (dual-mode): the `md_to_html` tool is exposed via
`__YOKER_MANIFEST__` for any yoker consumer to load.

The sister project `../yoker-writing-assistant` demonstrates
**yoker-as-runtime**: Yoker is the entry point and the package runs under
it as a plugin. Both are showcase packages for the Yoker 1.0 public
release.

The shared quality bar for both projects is in
[STANDARDS.md](STANDARDS.md): ultra clean code, tight right-tool-for-the-right-job
separation, limited but useful tests, and showcase quality. Both projects
inherit it; each carries its own copy kept in sync.

## The Two Core Principles

1. **Python owns the loop; the agent owns the reasoning.** No agent cost
   is spent on structured work (IMAP/SMTP plumbing); no Python is spent
   on reasoning. The two halves do not bleed.

2. **Dual-mode.** The package is simultaneously a consumer of yoker's
   built-in curated tools, a provider of its own named safe tool
   (`md_to_html`), and a reusable plugin. Self-consumption and
   third-party consumption use the identical mechanism.

## Conventions

- **Indentation**: Two spaces in all file types.
- **Package manager**: `uv` (see Makefile for standard targets).
- **Commit attribution**: `🤖 Implemented together with Yoker` as the trailer
  line on agent-made commits.
- **Fully qualified names**: In agent and skill definitions, use fully
  qualified names for tools (`yoker:read`), skills, and agents.
  Yoker supports bare-name resolution, but fully qualified is preferred in
  definitions for clarity and correctness.

## Current Project State

The project is release-ready. 48 tests green, lint clean, typecheck
clean, build clean. The only remaining task is publishing to PyPI. See
[`TODO.md`](TODO.md) for the full status and post-release backlog.

In place:

- `src/yoker_assistant/__init__.py` — Python package with
  `__YOKER_MANIFEST__` for plugin auto-discovery (tools + agents_dir)
- `src/yoker_assistant/__main__.py` — CLI entry point (`--once` flag)
- `src/yoker_assistant/loop.py` — the main async email-polling loop
- `src/yoker_assistant/tools.py` — the `md_to_html` custom tool
- `src/yoker_assistant/handler.py` — Rich UI handler for terminal output
- `src/yoker_assistant/agents/assistant.md` — the agent definition
- `pyproject.toml` — Python package definition (hatchling, uv, ruff, mypy)
- `Makefile` — standard targets (env-dev, test, check, run, docs, build,
  publish)
- `tests/test_loop.py`, `tests/test_import_safety.py`,
  `tests/test_md_to_html.py` — test suite
- `STANDARDS.md` — shared quality bar with yoker-writing-assistant
- `SECURITY.md` — manifest-addition review process
- `yoker.toml.example`, `.env.example` — reference templates
- `docs/` — Sphinx/ReadTheDocs documentation

## Module Structure

```text
src/yoker_assistant/
├── __init__.py              # __YOKER_MANIFEST__, version, import-safe
├── __main__.py              # CLI entry point: argparse + asyncio.run(run())
├── loop.py                  # Main async loop: poll, handoff, reply, archive
├── tools.py                 # Custom md_to_html tool (yoker plugin tool)
├── handler.py               # RichUIHandler for terminal output
├── py.typed                 # PEP 561 marker
└── agents/
    └── assistant.md         # Agent definition (Yoker-adapted)
```

### Key modules

- **`loop.py`** — The heart of the package. Constructs a `Session` once,
  runs the `Initialize` turn, polls IMAP for `UNSEEN`, hands each email
  to `session.agent.process()`, branches four ways on the reply
  (`{{NO_REPLY}}` / empty / unsafe HTML / valid HTML), sends via SMTP,
  marks read, archives. The `build_message` pure function produces the
  handoff payload. The `_contains_unsafe_html` guard catches agent
  regressions. No `Mailbox` or `Assistant` wrapper classes — both were
  descoped (the Wrapper Check: a wrapper must earn its behavior).

- **`tools.py`** — The `md_to_html` function converts markdown to an
  HTML body fragment. Annotated with yoker's `Text` guardrail. Cell
  content is HTML-escaped before wrapping to prevent XSS. The conversion
  logic is vendored from the heritage project with an escaping fix.

- **`handler.py`** — `RichUIHandler` extends yoker's `UIHandler` protocol
  for terminal output. Shows a banner, tool calls, diffs, errors, and
  status spinners during mailbox polling.

- **`__init__.py`** — Import-safe. Declares `__YOKER_MANIFEST__` with
  `tools=[md_to_html]` and `agents_dir="agents"`. No side effects at
  import time.

- **`agents/assistant.md`** — The agent definition. YAML frontmatter
  declares the bounded tool set. The body defines the workflow: Phase 1
  (Initialize / bootstrap), Phase 2 (Process), Phase 3 (Update), Phase 4
  (Reply via `md_to_html`).

## Agent Definition Format (Yoker)

Agent definitions are Markdown files with YAML frontmatter:

```yaml
---
name: assistant
description: |
  Short description for LLM tool definition.
tools:
  - yoker:read
  - yoker:write
  # ...
---
# System prompt body
```

Key fields:
- `tools`: Yoker-namespaced tool names. `ALL_TOOLS` (default) = all enabled
  tools. `[]` = no tools. Explicit list = filter to those.
- `model`: Optional model override.

## Agent Tool Set

The assistant gets a curated set of safe, named tools — no open shell:

- **File access**: `yoker:read`, `yoker:list`, `yoker:search`, `yoker:write`,
  `yoker:update`
- **Web**: `yoker:websearch`, `yoker:webfetch`
- **Skills & agents**: `yoker:skill`, `yoker:agent`
- **Git**: `yoker:git` (full git — read, commit, push)
- **Plugin tools**: `pkgq:find`, `yoker_assistant:md_to_html`

This is the safety model the showcase demonstrates: named, guardrailed
tools, never a shell. The heritage assistant had `Bash` — an open shell.
Yoker's model is the opposite.

## Tool Name Mapping (Heritage → Yoker)

The agent definition was adapted from a heritage project. Here is the
tool mapping:

| Heritage | Yoker | Notes |
|----------|-------|-------|
| `Read` | `yoker:read` | File contents with offset/limit |
| `Glob` | `yoker:list` | Directory listing with pattern |
| `Grep` | `yoker:search` | Content search (regex) + filename search |
| `Write` | `yoker:write` | Write file contents |
| `Edit` | `yoker:update` | Edit existing file (replace/insert/delete) |
| `Skill` | `yoker:skill` | Invoke a skill |
| `Agent` | `yoker:agent` | Spawn a sub-agent |
| `WebSearch` | `yoker:websearch` | Web search |
| `WebFetch` | `yoker:webfetch` | Fetch web content |
| `Bash` | *(removed)* | No open shell in yoker's safety model |
| `AskUserQuestion` | *(removed)* | No interactive UI; clarifications go in reply text |
| `PushNotification` | *(removed)* | No equivalent in unattended email mode |
| MCP email tools | *(removed)* | Email loop moved to Python |
| MCP resource tools | *(removed)* | Not part of yoker's tool model |
| MCP pkgq tool | `pkgq:find` | Loaded as a yoker plugin instead of MCP server |
| *(none)* | `yoker:git` | Full git (read, commit, push) |
| *(none)* | `yoker_assistant:md_to_html` | Custom tool defined in this package |

## Plugin Manifest

The package's `__init__.py` declares a `__YOKER_MANIFEST__`:

```python
from yoker.plugins import PluginManifest
from yoker_assistant.tools import md_to_html

__YOKER_MANIFEST__ = PluginManifest(
  tools=[md_to_html],
  agents_dir="agents",
)
```

This declares the custom tool and the agents directory. Yoker's plugin
loader discovers the agent definition automatically, namespacing it
under `yoker_assistant:`. When running the email loop, the package
self-injects plugin configuration in `loop.py` (enabled, packages,
trusted) — no user-side `[plugins]` config needed. External consumers
load the tool via their `~/.yoker.toml [plugins]` block.

## Launch / Entry Point

The package is started as a module or console script:

```bash
python -m yoker_assistant              # long-running loop
python -m yoker_assistant --once       # one iteration (demo/test)
# or after install:
yoker-assistant
yoker-assistant --once
```

`__main__.py` parses `--once` and calls `asyncio.run(run(once=args.once))`.

## Key Design Decisions

- **No `Mailbox` wrapper** — wrapping `IMAPClient`/`SMTPClient` in a
  third class added no behavior beyond forwarding. The loop calls them
  directly.
- **No `Assistant` wrapper** — same pattern around yoker's `Agent`.
  The loop constructs `Session` and calls `session.agent.process()`
  directly.
- **Persistent session** — one long-lived agentic session. The agent
  remembers the conversation across emails via yoker's context manager.
  No external session-state file.
- **Four-way reply branch** — `{{NO_REPLY}}` (intentional silence) /
  empty (transient problem) / unsafe HTML (guard failure) / valid HTML
  (normal reply). Each branch has specific mark-read/archive/send
  semantics.
- **Send before mark-read** — if the reply send fails, the message
  stays `UNSEEN` for retry. Mark read immediately after successful send,
  before archiving, to prevent duplicate replies on partial failure.
- **Connect/disconnect per iteration** — the poll interval is minutes;
  holding an idle IMAP connection would time out. Reconnect per
  iteration is simpler.

## Tool Output Discipline

**Always use `post_filter` on every tool call** to keep only relevant
lines. Tool outputs can be very large and consume context budget rapidly.

- `make test` / `make check`: filter for `FAILED|ERROR|Traceback|assert`
- `read` / `search` on large files: filter for structure markers
- `git log` / `git diff`: filter for the specific file or pattern