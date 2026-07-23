# Architecture

This page is the seam-by-seam reference for `yoker-assistant`. It is the
long-form companion to the [Tutorial](tutorial.md) (which tells the story)
and the source of truth in `analysis/functional.md` (which holds the spec).
Each section covers one seam in full.

## The two halves

The package is split between Python (the structured loop) and the agent (the
reasoning). Python owns the cheap structured work: mailbox connection,
search, fetch, reply send, mark-read, archive, sleep, error handling,
shutdown. The agent owns the reasoning: categorizing email content,
deciding what actions to take, using its curated tools to take them,
composing the reply in markdown, and converting it to HTML via its
`md_to_html` tool. No agent cost is spent on structured work; no Python is
spent on reasoning. The two halves do not bleed.

The seam between them is the loop module itself — the conceptual boundary
where the structured work (Python) hands off to the reasoning work (the
agent) and back. There is NO `Mailbox` wrapper class indirection layer and
NO `Assistant` wrapper around yoker's `Agent`. Both were proposed during the
build and both were descoped per owner feedback (the Wrapper Check — a
wrapper must earn its behavior; forwarding calls to two libraries from one
loop module IS the earned behavior of the loop; sub-wrapping each library
inside that is just indirection).

## The loop module

The package runs a single long-lived agentic session. At startup (once):
construct the `Agent` with a persistent context manager and run a
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

The agent REMEMBERS the running conversation across emails: continuity
lives in the persistent session (yoker's context manager) plus memory files
and `PERSONAL.md` learned behaviours the agent writes.

## The yoker SDK seam

Yoker is a library-first, async, event-driven agent harness. The public SDK
surface is:

```python
from yoker.config import get_yoker_config
from yoker.session import Session

config = get_yoker_config()
config.agent = "yoker_assistant:assistant"  # resolved by name from the registry
# Session is constructed ONCE at startup and owns the agent registry, the
# primary Agent, persistence (via config.context), and the `agent` tool.
async with Session(config, session_id="yoker-assistant") as session:
    agent = session.agent
    response = await agent.process(message)  # returns the agent's text
```

Key facts of the seam:

- `Session(config, *, session_id=None, ...)` requires a `Config` object;
  config is discovered from `./yoker.toml` then `~/.yoker.toml` via
  `get_yoker_config()`. `config.agent` is set programmatically to
  `yoker_assistant:assistant` so Session resolves the assistant by name
  from the plugin-loaded `AgentRegistry` (no manual definition loader).
- `session.agent.process(message) -> str` is async and returns the agent's
  final text response. Tool calls happen internally during `process`.
- A persistent context manager keeps the running conversation across
  `process()` calls; the Session is constructed once and lives for the
  whole package run (the loop body is inside the `async with Session:`
  block).
- Agent definitions are markdown files with YAML frontmatter (`name`,
  `description`, `tools`, optional `model`). Built-in tools may be referenced
  with or without the `yoker:` prefix and are matched case-insensitively;
  plugin tools must use their full namespace (e.g. `pkgq:find`).
- Tools are plain Python functions/callables annotated with guardrail
  markers (`Path`, `Url`, `Query`, `Text`). Plugins expose tools, skills,
  and agents via a top-level `__YOKER_MANIFEST__`.
- Skills are loaded from configured `skills/` directories and invoked via
  the `yoker:skill` tool or `agent.inject_skill_context(name, args)`.

The whole project hinges on this seam. It is usable today (yoker 0.8.0):
`Agent` + `agent_definition` + `process` is sufficient.

## The simple-email-gw seam

`simple-email-gw` provides async `IMAPClient`/`SMTPClient` and a
`ConnectionPool` that reads `EMAIL_*` env vars via `ServerConfig`. The
async API:

```python
from simple_email_gw import get_pool

pool = await get_pool()
imap = await pool.get_imap_client("default")
smtp = await pool.get_smtp_client("default")

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

await smtp.reply_email(to=[sender], subject=f"Re: {subject}",
                       html_body=reply_html, in_reply_to=msg_id)
```

`simple_email_gw` 0.3.0 `IMAPClient`/`SMTPClient` are NOT async context
managers; they expose explicit `connect()`/`disconnect()` methods. The loop
calls those methods directly. There is NO `Mailbox` wrapper class.

Connection lifetime: the loop does NOT hold the IMAP connection open across
the multi-minute poll interval. Each iteration bookends with `connect()` /
`disconnect()`. A dropped connection mid-iteration surfaces as a
per-message exception (logged, message left `UNSEEN`, retried next iteration
with a fresh connection); no reconnect-on-failure guard is needed. SMTP is
fire-and-forget per send.

`EmailAccount` fields: `name`, `imap_host`, `smtp_host`, `username`,
`password`. Configuration is read by the SDK's `ServerConfig` from env vars
(`EMAIL_IMAP_HOST`, `EMAIL_SMTP_HOST`, `EMAIL_USERNAME`, `EMAIL_PASSWORD`)
or a multi-account JSON (`EMAIL_ACCOUNTS_JSON`). The loop does not parse
these — it passes the literal account name `"default"` to the pool.

## The handoff contract

### What Python hands to the agent

Each incoming email is delivered to the SAME session as the next user
message via `agent.process(message)`. The message is a single string
carrying only the email itself — no instructions block:

```
From: <sender name> <sender@email>
Subject: <original subject>
Date: <rfc date>

<body of the email, as plain text>
```

`build_message` in `loop.py` is a pure function that produces this format
from the raw `simple_email_gw` message dict. CR/LF is collapsed in header
values to prevent handoff-format injection; the body is passed through
verbatim. No `Instructions:` block is sent. Identity lives in the agent
definition and the one-time session-setup step, not in each email payload.

### What the agent returns

The agent composes its reply in markdown, then calls the custom
`yoker_assistant:md_to_html` tool to convert it to HTML. `Agent.process()`
returns that HTML string. That string IS the reply body. Python does not
interpret it or re-render it; it sends the HTML verbatim as the email body
(subject `Re: <original subject>`, to the sender). Markdown and email do not
render well together, so the reply is HTML end-to-end.

### Conversation-style logging

`_process_one` in `loop.py` emits two `logger.info` calls framing the
conversation between user and agent — one before `agent.process` (the
incoming handoff, "user turn") and one after (the agent's reply, "agent
turn"), with `===` separators so the two turns are visible in normal
INFO-level log output. An empty reply is logged explicitly as
`"(empty — no reply)"` so a silent agent turn still shows up in the
conversation log. The one-time `Initialize` setup turn is NOT logged — it
is a session-setup handshake, not an incoming message.

### How Python turns that into a reply

1. Capture `reply_html = await agent.process(message)`.
2. Four-way branch on `reply_html`:
   - `{{NO_REPLY}}` sentinel: mark `\Seen` and archive. No reply.
   - empty/whitespace: leave `UNSEEN`, retry next iteration.
   - unsafe HTML (guard failure): mark `\Seen` (no archive), send plain-text
     notice to sender.
   - valid HTML: send via `reply_email(html_body=reply_html, ...)`, then
     mark `\Seen` and archive.
3. Every send is a reply — always `reply_email`; there is NO `send_email`
   fallback. `to` is a bare address string extracted via
   `parseaddr(msg["from"])[1]`. `body=""` is required by `reply_email`'s
   signature; the plain-text alternative is intentionally empty in the
   first pass (accessibility polish deferred).
4. Ordering (valid-reply branch): send → mark read → archive. Send before
   marking read so a send failure leaves the message `UNSEEN` for retry.
   Mark read immediately after a successful send, before archiving.

### Ordering and idempotency

- Process one email per loop iteration (simplest, safest for a showcase).
  Batching is a later optimization, out of scope.
- Idempotency relies on IMAP flags, exactly as the heritage `pa-email` skill
  did: `UNSEEN` search returns only unprocessed messages; mark-read +
  archive ensures a message never reappears. No deduplication state is
  needed.
- The ordering (send → mark read → archive) is owned by the loop module.
- Critical ordering: send the reply BEFORE marking read/archiving. If the
  reply fails, do not mark read — the message stays `UNSEEN` and is retried
  next iteration. If the reply succeeds but mark/archive fails, the message
  is still `UNSEEN`; next iteration it will be reprocessed and a duplicate
  reply sent. To avoid duplicates on this partial-failure path, Python
  marks read IMMEDIATELY after a successful send, before archiving. A
  marked-read-but-not-archived message is excluded from `UNSEEN`, so it
  will not be reprocessed; it just lingers in INBOX until the next loop
  tidies it. This is acceptable and documented.

## The bounded tool set

The agent's curated tool set is declared in the `tools:` frontmatter of
`src/yoker_assistant/agents/assistant.md`:

- `yoker:read`, `yoker:list`, `yoker:search` — read access
- `yoker:write`, `yoker:update` — write access
- `yoker:websearch`, `yoker:webfetch` — online access
- `yoker:skill` — invoke loaded skills
- `yoker:agent` — bounded subagent spawning (1 level)
- `yoker:git` — full git (read + commit + push). This is part of the
  showcase: the agent autonomously maintains its own `PERSONAL.md`
  learned-behaviours file in version control via bounded git tools, not a
  shell.
- `pkgq:find` — via the pkgq plugin (demonstrates yoker plugin loading)
- `yoker_assistant:md_to_html` — a custom local tool defined in THIS
  package as a yoker plugin.

This set is deliberately small. It demonstrates yoker's safety model:
named, guardrailed tools, no open shell — and it shows both modes of tool
authorship (consume built-ins, define your own).

## The persistent-session architecture

The package runs ONE long-lived agentic session. The `Agent` is constructed
ONCE at startup with a persistent context manager; each email is the next
user message in that session. The agent remembers the running conversation
across emails; continuity lives in the persistent session (yoker's context
manager) plus memory files and `PERSONAL.md` learned behaviours the agent
writes (and commits via `yoker:git`).

Context-window growth (compaction, summarization, trimming) is yoker's
responsibility, not this package's. The package uses yoker's persistent
context manager and trusts yoker to handle context-window growth. It is
out of scope by design because it is yoker's job.

## Dual-mode architecture

`yoker-assistant` is BOTH a standalone yoker SDK consumer AND a yoker
plugin provider. This is the design-intended pattern — yoker itself is
dual-mode.

- The `md_to_html` tool is defined in `src/yoker_assistant/tools.py` as a
  plain Python function with yoker tool annotations
  (`Annotated[str, Text(...)]`).
- `__YOKER_MANIFEST__ = PluginManifest(tools=[md_to_html],
  agents_dir="agents")` is exposed in `src/yoker_assistant/__init__.py`. The
  `agents_dir` field tells the yoker plugin loader to discover
  `agents/*.md` inside the installed `yoker_assistant` package — so
  external yoker consumers can reference the assistant agent by name
  (`yoker_assistant:assistant`) from their `Session`'s registry.
- The user adds the plugin registration to their `~/.yoker.toml`:
  `[plugins] enabled = true; packages = ["yoker_assistant", "pkgq"]` and
  `[plugins.trusted] yoker_assistant = true; pkgq = true`.
- The `Agent` is resolved by name (`yoker_assistant:assistant`) from the
  `Session`'s `AgentRegistry`, which the plugin loader populates from the
  installed package's `agents/` directory. No manual definition loader,
  no relative filesystem path that would break when the package is
  installed.
- External consumers load yoker-assistant's tools the IDENTICAL way:
  `pip install yoker-assistant` plus the same `[plugins]` /
  `[plugins.trusted]` lines in their `~/.yoker.toml`. Self-consumption and
  third-party consumption use the same mechanism — this is the elegant
  showcase point.

This adds a THIRD layer to the demo: (1) consumer of yoker's built-in
curated tools, (2) provider of its own named safe tool, (3) reusable —
any yoker consumer can load the tool. Minimal cost: one manifest
declaration plus three lines in the user's `~/.yoker.toml`.

## The custom md→html tool

The `md_to_html` tool converts a markdown string to an HTML body fragment
(no `<html>` wrapper). It is defined in `src/yoker_assistant/tools.py` as
a plain Python function annotated with yoker tool guardrails. The
manifest declaration in `src/yoker_assistant/__init__.py` is five lines:

```python
from yoker.plugins import PluginManifest
from yoker_assistant.tools import md_to_html

__YOKER_MANIFEST__ = PluginManifest(
  tools=[md_to_html],
  agents_dir="agents",
)
```

The `__init__.py` is import-safe: importing it must NOT trigger any Agent
construction, email logic, or loop logic. Those live in `__main__`, `loop`,
and `agent`. The manifest only declares tool functions — no side effects at
import time. This discipline avoids any circular import.

The tool handles headers, bold, tables, lists, horizontal rules, and
paragraphs. Cell content is HTML-escaped before wrapping in tags so the
agent cannot inject arbitrary HTML through the table converter; the
`**` marker survives escaping, so bold still works, and the
`<strong>/</strong>` tags are added by the tool, not from input. Email
wrapping and sending is the loop's job, not this tool's.

## Loop behavior

- **Poll interval:** 60 seconds (the `_POLL_INTERVAL` constant in
  `loop.py`).
- **No email:** sleep and repeat. Never error on an empty inbox.
- **Per-message flow:** fetch → handoff → reply → mark read → archive,
  with the ordering above.
- **Error handling:**
  - IMAP/SMTP connection failure: per-iteration exception, logged, message
    left `UNSEEN`, retried with a fresh connection next iteration.
  - Agent `process` failure (e.g. backend network error): logged, do NOT
    mark read, continue to next message or next iteration. The message
    retries on the next `UNSEEN` search.
  - Reply send failure: do not mark read; retry next iteration.
  - Guard failure (unsafe HTML in agent output): mark `\Seen` (no archive)
    and send a plain-text notice to the original sender. The owner
    controls reprocessing by removing `\Seen`.
  - Empty/whitespace reply (transient): leave `UNSEEN`, no mark/archive,
    retry next iteration. The `{{NO_REPLY}}` sentinel is the agent's
    intentional-silence signal and is handled separately (mark + archive).
  - Unexpected exception per message: log, skip the message (leave it
    `UNSEEN` so it is retried), continue the loop.
  - **C1 startup guard:** the loop refuses to start when the recipient
    whitelist is disabled — the whitelist fails open, so an unset
    whitelist would let the assistant reply to arbitrary senders. `run()`
    raises `RuntimeError` before constructing the `Agent`.
- **Graceful shutdown:** on `SIGINT`/`SIGTERM`, stop accepting new
  messages, finish the in-flight message, close connections, exit 0.
- **No background concurrency in the first pass:** one loop, one message
  at a time. Simple and demonstrable.

## Entry point

The package is started as a module / console script:

```
python -m yoker_assistant
# or, after install:
yoker-assistant
```

It runs `asyncio.run(main())`, which constructs the `Agent` once, runs the
one-time session-setup step (agent reads `PERSONAL.md` and initializes), and
enters the loop. A `--once` flag processes a single iteration and exits
(useful for tests and demos). Graceful shutdown on `SIGINT`/`SIGTERM`:
finish the current message, close IMAP/SMTP connections, exit.