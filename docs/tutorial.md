# Tutorial — How yoker-assistant Was Built

This page tells the build story of `yoker-assistant` end-to-end. A reader who
finishes it understands why the package exists, what the two halves are, how
the seams between them work, what the agent is allowed to do, how the session
stays alive across emails, and how the package doubles as a reusable yoker
plugin. It is a narrative — not a reference, not a list of links. The
functional spec (`analysis/functional.md` in the repo) is the source of truth
for the design; this page tells the story of how that design was realised.

The package is small on purpose. It is one of two yoker 1.0 pet-store
showcases; its job is to demonstrate yoker-as-SDK — Python owns the loop and
imports yoker as a library for the reasoning half. Every decision below is in
service of that demonstration.

---

## 1. Why this exists

The heritage assistant lives in `../c3/agents/assistant.md` and runs inside
Claude Code. In that model, the **agent** does the cheap recurring structured
work of polling an email inbox via an MCP email server
(`mcp__plugin_c3_email__*` tools). The agent wakes on a `/loop 30m /pa-email`
schedule, lists `UNSEEN`, fetches each message, categorizes, takes actions,
composes a reply, sends it, marks the original read, archives it, and sleeps
until the next tick. All of that is structured work — IMAP and SMTP plumbing,
flag bookkeeping, archive moves — and none of it needs a language model. It
needs a loop and a mailbox client. Paying per-token agent cost to drive IMAP
search is the pattern this project eliminates.

The insight is that the email loop is cheap structured work that should live
in Python, not in the agent. Python polls the mailbox, fetches messages,
sends replies, and archives originals. The agent is left to do what it is
good at — reasoning about the email content, deciding what to do, using
bounded tools to do it, and composing the reply. No agent cost is spent on
structured work; no Python is spent on reasoning.

The port therefore does two things. **First, it moves the email loop into
Python.** Python polls the mailbox via the `simple-email-gw` package, parses
messages, and sends replies. The MCP email-server tools and the inbox-checking
logic are removed from the agent. **Second, it wraps the slimmed agent in a
Python loop that calls yoker as an SDK.** When Python detects an email, it
hands the content to the agent via yoker's `Agent.process()`. The agent
reasons and replies; Python sends the reply via `simple-email-gw`.

The result is a standalone Python package that runs unattended on the host it
is started on. The owner emails it; it reasons about the email, acts on the
owner's behalf using a curated set of safe tools, and emails back. The inbox
is the entire UI: no TUI, no CLI prompts, no web. This is the smallest
interesting demonstration of yoker-as-SDK — and the foundation for the
dual-mode story (§9) that makes the package reusable by any external yoker
consumer.

## 2. The two halves

The central design idea is the split between Python and the agent. Python
owns the cheap structured loop: mailbox connection, search, fetch, reply
send, mark-read, archive, sleep, error handling, shutdown. The agent owns
the reasoning: categorizing email content, deciding what actions to take,
using its curated tools to take them, composing the reply in markdown, and
converting it to HTML via its `md_to_html` tool. No agent cost is spent on
structured work; no Python is spent on reasoning. The two halves do not
bleed.

```
+-------------------------+        handoff        +-------------------------+
| Python (the loop)       |  ------------------->  | The agent (yoker SDK)   |
|                         |   From/Subject/Date     |                         |
|  poll IMAP UNSEEN       |   + body                |  categorize, decide,   |
|  fetch each message     |  <-------------------   |  act with bounded tools|
|  send reply via SMTP    |   HTML reply (or        |  compose reply in MD,   |
|  mark read, archive     |   {{NO_REPLY}}/empty)   |  convert to HTML       |
|  sleep, repeat          |                        |                         |
+-------------------------+                        +-------------------------+
| simple-email-gw seam    |                        | yoker SDK seam          |
+-------------------------+                        +-------------------------+
```

The seam between the two halves is the loop module itself — the conceptual
boundary where the structured work (Python) hands off to the reasoning work
(the agent) and back. There is NO `Mailbox` wrapper class indirection layer:
the loop calls `simple_email_gw`'s `IMAPClient` and `SMTPClient` directly. An
earlier design proposed a `Mailbox` seam class; it was descoped per owner
feedback during P1-003 — wrapping two existing classes in a third class
added no benefit for a demo/tutorial. The same happened with an `Assistant`
wrapper around yoker's `Agent` during P1-004 — same useless-wrapper pattern,
same descope. The loop drives `Session.agent` directly and calls
`IMAPClient`/`SMTPClient` directly. Two seams, no wrappers.

## 3. The seams

The two seams are deliberately thin. Each is a small number of calls in
`src/yoker_assistant/loop.py` against a library that owns the hard part.

### The yoker SDK seam

Yoker is a library-first, async, event-driven agent harness. The assistant
agent is resolved by name from the `Session`'s plugin-loaded registry — no
manual definition loader, no file path that breaks when the package is
installed. The loop constructs a `Session` once, sets `config.agent =
"yoker_assistant:assistant"`, and the registry resolves the agent definition
packaged at `src/yoker_assistant/agents/assistant.md` via the manifest's
`agents_dir="agents"` field.

The seam in `loop.py` is five lines:

```python
config = get_yoker_config()
config.agent = "yoker_assistant:assistant"

async with Session(config, session_id="yoker-assistant") as session:
    agent = session.agent
    reply_html = await agent.process(handoff)
```

The `Session` owns the agent registry, the `agent` tool, and clean shutdown.
`agent.process(message) -> str` is async and returns the agent's final text
response; tool calls happen internally during `process`. A persistent context
manager keeps the running conversation across `process()` calls — this is
what makes the per-email "next user message" model work (§7).

### The simple-email-gw seam

`simple-email-gw` provides async `IMAPClient`/`SMTPClient` and a
`ConnectionPool` that reads the `EMAIL_*` env vars via `ServerConfig`. The
loop only knows the account name (`"default"` — the SDK convention); it does
not parse `EMAIL_*` env vars itself. The pool returns cached but
NOT-yet-connected clients, so the loop calls `connect()` explicitly per
iteration.

The seam in `loop.py`:

```python
pool = await get_pool()
imap = await pool.get_imap_client("default")
smtp = await pool.get_smtp_client("default")  # fire-and-forget per send

while not stop.is_set():
    await imap.connect()
    try:
        uids = await imap.search("INBOX", "UNSEEN")
    finally:
        await imap.disconnect()
```

The `connect()`/`disconnect()` bookend each iteration deliberately. The poll
interval is several minutes, so holding an idle connection open across the
sleep would just time out server-side every time — reconnecting per iteration
is simpler and avoids the reconnect-on-failure guard entirely. The first
iteration's `connect()` is also the credential check (no startup fast-fail
connect outside the loop). `SMTPClient` is fire-and-forget per send (no
`connect()`/`disconnect()`); `reply_email` opens and closes its own
connection per call.

### Why no wrappers

Both seams are thin on purpose. An earlier design proposed a `Mailbox` class
wrapping `IMAPClient`/`SMTPClient`, with `connect()`/`unread_ids()`/`fetch()`/
`reply()`/`mark_read()`/`archive()`/`close()` methods. The owner challenged
this during P1-003 review — "Why wrap two existing classes in another class
with no added benefit?" — and the consensus was that the wrapper added no
behavior beyond forwarding and failed the Wrapper Check. The same happened
with an `Assistant` class around yoker's `Agent` during P1-004 — same
useless-wrapper pattern, same descope. The lesson, recorded in
`STANDARDS.md`'s "tight code" section: a wrapper must earn its behavior.
Forwarding calls to two libraries from one loop module IS the earned
behavior of the loop; sub-wrapping each library inside that is just
indirection.

## 4. The handoff contract

The handoff is the most important seam in the project. It defines exactly
what Python hands to the agent and what the agent returns.

### What Python hands to the agent

The package runs one long-lived agentic session. The agent's identity,
workflow, categorization rules, and guardrails live in the agent definition
(`src/yoker_assistant/agents/assistant.md`, packaged inside this package and
loaded by yoker as the system prompt) — NOT in the per-email payload. At
startup, the package constructs the `Agent` once and sends a ONE-TIME
`Initialize` message to the session before the loop begins. The agent reads
`PERSONAL.md` on that first turn and initializes identity for the ongoing
session. After that, each incoming email is the next user message in the SAME
session. The setup is not repeated per email.

Each incoming email is delivered to that session as the next user message via
`agent.process(message)`. The message is a single string carrying only the
email itself — no instructions block:

```
From: <sender name> <sender@email>
Subject: <original subject>
Date: <rfc date>

<body of the email, as plain text>
```

The `build_message` function in `loop.py` is a pure function that produces
this format from the raw `simple_email_gw` message dict. CR/LF is collapsed in
the header values to prevent handoff-format injection; the body is passed
through verbatim. No `Instructions:` block is sent. Identity lives in the
agent definition and the one-time session-setup step, not in each email
payload.

### What the agent returns

The agent composes its reply in markdown, then calls the custom
`yoker_assistant:md_to_html` tool to convert it to HTML. `Agent.process()`
returns that HTML string. That string IS the reply body. Python does not
interpret it or re-render it; it sends the HTML verbatim as the email body
(subject `Re: <original subject>`, to the sender). Markdown and email do not
render well together, so the reply is HTML end-to-end (§8 covers the tool).

### The four-way branch on the reply

Python branches four ways on what the agent returned:

- **`{{NO_REPLY}}` sentinel present** — intentional silence. Mark the
  original `\Seen` and archive it. No reply is sent. The sentinel is the
  agent's explicit "I chose not to reply" signal; it is never used for
  anything else.
- **empty/whitespace reply** — transient problem. Leave the message `UNSEEN`
  so it is retried next iteration. No mark, no archive, no send. An empty
  reply is a signal something went wrong inside the agent turn, not a
  decision to stay silent.
- **unsafe HTML (guard failure)** — `<script>`, `<style>`, `<img>`,
  `<iframe>`, `<object>`, `<embed>`, `<form>` or `on*=` event handlers in
  the reply. Mark the original `\Seen` (do NOT archive — the owner controls
  reprocessing by removing `\Seen`), and send a plain-text notice to the
  original sender via `reply_email(to=sender, body=notice, ...)`. No HTML
  body is sent in this branch.
- **valid HTML reply** — send via
  `smtp.reply_email(to=sender, subject=f"Re: {subject}", body="",
  html_body=reply_html, in_reply_to=message_id)`, then mark `\Seen` and
  archive.

The unsafe-HTML guard lives in the loop, not in the agent. The agent is
trusted to produce HTML (it owns the reply), but a defence-in-depth check
catches the case where a model regression emits something the agent should
not have. The guard is a small regex over the lowered reply string.

### Every send is a reply

There is no `send_email` fallback. Every send uses `smtp.reply_email(...)`
with `in_reply_to=msg["message_id"]` so threading is preserved in the
recipient's client. `to` is a bare address string extracted via
`parseaddr(msg["from"])[1]` — the gateway's `validate_email` rejects
display-name headers, so the bare address is required. `body=""` is required
by `reply_email`'s signature; the plain-text alternative is intentionally
empty in the first pass (accessibility polish is deferred).

### Ordering and idempotency

The ordering on the valid-reply branch is **send → mark read → archive**.
Send before marking read so a send failure leaves the message `UNSEEN` for
retry. Mark read immediately after a successful send, before archiving, so
the message is excluded from `UNSEEN` even if the archive move fails — a
marked-read-but-not-archived message lingers in INBOX until the next loop
tidies it, but it is not reprocessed (no duplicate reply). Idempotency
relies on IMAP flags, exactly as the heritage `pa-email` skill did: `UNSEEN`
search returns only unprocessed messages; mark-read + archive ensures a
message never reappears. No deduplication state is needed.

The ordering is owned by the loop module — there is no `Mailbox` seam object
that owns it. The loop sequences the calls to `IMAPClient`/`SMTPClient`
directly, in the order that makes partial-failure recovery cheap.

## 5. The bounded tool set

The agent's tools are declared in the `tools:` frontmatter of
`src/yoker_assistant/agents/assistant.md`. The set is deliberately small —
named, guardrailed tools, no open shell. This is part of what the showcase
demonstrates.

| Tool | Purpose |
|---|---|
| `yoker:read` | Read file contents (PERSONAL.md, project guidance, memory) |
| `yoker:list` | Directory listing with pattern/depth filtering |
| `yoker:search` | Regex/glob content search with complexity limits |
| `yoker:write` | Write files with overwrite protection |
| `yoker:update` | Edit files (replace/insert/delete with diffs) |
| `yoker:websearch` | Web search with SSRF and rate-limit guardrails |
| `yoker:webfetch` | Fetch web content with URL validation |
| `yoker:skill` | Invoke loaded skills dynamically by name |
| `yoker:agent` | Spawn isolated subagents (1 level of recursion) |
| `yoker:git` | Full git — read, commit, push (the demo beat in §10) |
| `pkgq:find` | Package documentation lookup (via the pkgq plugin) |
| `yoker_assistant:md_to_html` | Convert markdown reply to HTML (this package's own tool — §8) |

The safety model is the point. The heritage c3 assistant had `Bash` — an
open shell. yoker's safety model is the opposite: agents get a curated set of
safe, named tools, never an open shell. Each tool has guardrails (path
restrictions, URL validation, complexity limits); the agent cannot escape
them because the tool itself enforces them, not a prompt. `Bash` is removed;
`AskUserQuestion` and `PushNotification` (Claude Code UI concepts) are
removed; the MCP email tools are removed (the email loop moved to Python);
the MCP resource tools are removed. What is left is a small, auditable
surface that the agent uses to act on the owner's behalf.

`yoker:git` is full git — read, commit, push — not a read-only view. This is
part of the showcase: the agent autonomously maintains its own `PERSONAL.md`
learned-behaviours file in version control via bounded git tools, not a
shell (§10). The blast radius is real (the agent can push to the configured
remote) and is bounded by the trust gate (§9) and by the recipient whitelist
(§11).

## 6. The c3 → yoker-assistant porting map

The adaptation principle, stated once: keep the concepts — what an agent is,
what a skill is — and rework the mechanics for the yoker context. c3 runs
inside Claude Code with its own orchestrator; yoker is an SDK/runtime with
different mechanics. For each adapted piece, what is kept verbatim and what
is reworked is stated explicitly. The full per-element table is on the
[Porting Map](porting-map.md) page; the condensed verdicts are here.

**KEPT** — the assistant concept and identity; the agent definition format
(markdown + YAML frontmatter); the core reasoning workflow (categorize → act
→ reply); item categorization rules; memory creation; the reply format; the
curated read/write/web/skill/agent tool set. Reading `PERSONAL.md` at session
start is kept AS-IS from c3, and so is writing to it (the agent adds learned
behaviours for later, via `yoker:update`/`yoker:write`).

**REMOVED** — all MCP email tools (the central reason the project exists);
the `pa-email` skill; `Bash` (yoker's safety model — no open shell); the
Claude Code UI tools `AskUserQuestion` and `PushNotification`; the MCP
resource tools; the file inbox/outbox/archive I/O from `pa-inbox` and
`pa-outbox`; the `color` frontmatter field (a Claude Code UI hint).

**REWORKED** — `Glob` → `yoker:list` (yoker has `list`, not a separate
`Glob`); `Grep` → `yoker:search`; `Edit` → `yoker:update`; the pkgq tool from
an MCP server (`mcp__plugin_c3_pkgq__find_package`) to a yoker plugin
(`pkgq:find`); `pa-inbox` from a file-based inbox processor to a
reasoning-only skill over the email handoff; `pa-outbox` from a file-based
outbox writer to a reply-format skill that ends in HTML via `md_to_html`.

**DROPPED** — `pa-session`. The heritage skill maintained `session-state.md`
for continuity across iterations. yoker's persistent context manager
(§7) carries session state natively across `process()` calls — the agent
remembers the running conversation across emails without an external state
file. On top of that, the agent writes memory files and `PERSONAL.md` learned
behaviours. There is no job left for `pa-session`; keeping it would be dead
surface area. Dropped and documented.

**ADDED** — `yoker_assistant:md_to_html`. A custom local tool defined in THIS
package as a yoker plugin (§8). This is the showcase's "create your own
bounded tool" example and pairs with the built-in curated tools above to
demonstrate both halves of yoker's tool model: using built-ins AND authoring
your own.

## 7. The persistent-session architecture

The package runs ONE long-lived agentic session. The `Agent` is constructed
ONCE at startup with a persistent context manager; it is NOT reconstructed
per email. The `Session` is entered via `async with Session(config,
session_id="yoker-assistant") as session:` and the loop body lives inside
that block so the Session owns the agent registry, the `agent` tool, and
clean shutdown.

Before the loop begins, the package sends a one-time `Initialize` message to
the session:

```python
async with Session(config, session_id="yoker-assistant") as session:
    agent = session.agent
    await agent.process(_INITIALIZE_PROMPT)   # "Initialize"
    # ... then the poll loop ...
```

On that first turn, the agent reads `PERSONAL.md` via `yoker:read`. If
`PERSONAL.md` exists, it establishes identity and learned behaviours for the
ongoing session. If it does not exist (first run, bootstrap), the agent
replies with a welcome message and a set of questions for the owner; the
owner answers by replying over email; the agent iterates with the owner
until it has enough to write the initial `PERSONAL.md` (and optionally
commit + push it via `yoker:git` — §10).

After the `Initialize` turn, every incoming email is the next user message in
that SAME session. The agent remembers the running conversation across
emails — continuity lives in the persistent session (yoker's context
manager), plus memory files the agent writes via `yoker:write`, plus
`PERSONAL.md` learned behaviours the agent writes via `yoker:update`. The
session is not re-initialized per email; the `Initialize` turn is not
repeated. This is why `pa-session` was dropped (§6): the context manager
already carries the state `pa-session` used to maintain in a file.

Context-window growth (compaction, summarization, trimming) is yoker's
responsibility, not this package's. The package uses yoker's persistent
context manager and trusts yoker to handle context-window growth. It is
out of scope by design because it is yoker's job.

## 8. The custom md→html tool story

The showcase's "create your own bounded tool" example is a plain Python
function in `src/yoker_assistant/tools.py` annotated with yoker guardrail
markers, exposed via `__YOKER_MANIFEST__` in `src/yoker_assistant/__init__.py`.

The tool is small — it converts a markdown string to an HTML body fragment
(no `<html>` wrapper). Headers, bold, tables, lists, horizontal rules, and
paragraphs are handled; cell content is HTML-escaped before wrapping so the
agent cannot inject arbitrary HTML through the table converter. Email
wrapping and sending is the loop's job, not this tool's — the tool returns an
HTML fragment; the loop puts it in the reply body.

The manifest declaration in `src/yoker_assistant/__init__.py` is five lines:

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

Why HTML, not plain text? Markdown and email do not render well together. A
markdown reply arrives at the recipient's client as raw markdown source — no
headings, no tables, no bold. The agent's reply is rich (Actions Taken
tables, Memory Created sections, Pending Questions), and that richness is
lost if the reply is sent as markdown. The agent composes in markdown (its
natural format), then converts to HTML via this tool, and the loop emails the
HTML verbatim. The recipient sees a rendered email, not a code block.

Why this is the second half of yoker's tool model — the package is BOTH a
consumer of yoker's built-in curated tools (§5) AND a provider of its own
named safe tool (`yoker_assistant:md_to_html`). Using built-ins demonstrates
one half; authoring your own demonstrates the other. The custom tool is
plugin-registered, so any external yoker consumer can load it the same way
the package itself does (§9). This is the design-intended pattern — yoker
itself is dual-mode.

## 9. Dual-mode architecture

The package is simultaneously three layers of yoker's tool model:

1. **Consumer** of yoker's built-in curated tools — `yoker:read`,
   `yoker:write`, `yoker:git`, etc. The agent declares these in its `tools:`
   frontmatter and yoker resolves them at session startup.
2. **Provider** of its own named safe tool — `yoker_assistant:md_to_html`.
   The tool is defined in this package, exposed via `__YOKER_MANIFEST__`,
   and registered via the user's `~/.yoker.toml [plugins]` block (NOT
   programmatic — no `plugins=()` arg to `Agent`).
3. **Reusable plugin** — any external yoker consumer can load the tool
   identically. `pip install yoker-assistant` plus the same two lines in
   their `~/.yoker.toml`:
   ```toml
   [plugins]
   enabled = true
   packages = ["yoker_assistant"]

   [plugins.trusted]
   yoker_assistant = true
   ```
   Self-consumption and third-party consumption use the identical mechanism.
   This is the elegant showcase point: there is no "internal" API and
   "external" API — there is one plugin API, and the package uses it on
   itself the same way a stranger would.

### The self-trust requirement

With no TTY to prompt, yoker's trust gate rejects untrusted plugins in
non-interactive mode. The package runs unattended (the loop has no UI), so
the user must mark the package trusted in `~/.yoker.toml`:

```toml
[plugins.trusted]
yoker_assistant = true
pkgq = true
```

The blast radius: marking `[plugins.trusted] yoker_assistant = true` admits
ALL tool code from this package as trusted with no per-call gate. The trust
decision is made once, at install time. Pin the installed version
(`uv pip install yoker-assistant==<version>`) and verify the source. Adding
a new tool to `__YOKER_MANIFEST__`, or making a capability-changing edit to
an existing tool, is a security-relevant change; see [Security](security.md)
for the review process contributors must follow before such a change.

Self-trust is a single line in `~/.yoker.toml`. It is what makes unattended
operation possible; it is also what makes the blast radius real. Both are
the intended yoker trust model — the user takes the trust decision at
install time, once, and the package's tools then run without per-call
interruption.

### Why the three layers matter together

The three layers compose into the showcase's central point. Layer 1
(consumer) demonstrates that yoker's built-in curated tools are useful out
of the box — the agent can read files, search the web, spawn subagents,
commit and push, without the package author writing any of that. Layer 2
(provider) demonstrates that authoring a bounded tool is a small, named,
guardrailed affair — five lines of manifest, one plain function, no
boilerplate. Layer 3 (reusable) demonstrates that the plugin model is
symmetric — the package uses itself exactly the way a stranger would use
it. Together they show that yoker-as-SDK is not a "use the library OR write
a plugin" choice; it is a "use the library AND write a plugin AND let others
use your plugin" stack, with one consistent mechanism for all three. The
`yoker-assistant` package is the smallest interesting demonstration of that
stack.

## 10. The git commit/push demo beat

The visible "acts on behalf of the owner" moment is the agent autonomously
maintaining its own `PERSONAL.md` learned-behaviours file in version
control. The flow:

1. The owner emails the assistant a preference — "from now on, always CC me
   on replies to staging-deploy emails" or similar.
2. The agent categorizes this as a learned behaviour (not a one-off action),
   updates `PERSONAL.md`'s `## Behaviors` section via `yoker:update`, and
   composes a short reply acknowledging the change.
3. The agent then commits the `PERSONAL.md` change and pushes via
   `yoker:git` (full git, not a shell). The commit lands in the configured
   remote; the push is bounded by the trust gate (§9) and by yoker's
   `git` tool permissions (`filesystem_paths`, remote allowlist).
4. The agent's reply is converted to HTML via `md_to_html` and returned
   from `process()`. Python emails it as the reply.

This is the showcase's headline demonstration of bounded tools acting on the
owner's behalf. The agent does not have a shell — it cannot run arbitrary
commands. It has `yoker:git`, a named tool with a bounded surface (read,
commit, push), and it uses that tool to maintain its own state file in
version control. The owner sees the commit appear in the repository; the
assistant has acted on the owner's behalf, autonomously, within a bounded
tool surface.

The loop logs the user turn and the agent turn with `===` separators so the
demo is visible at INFO level during the iteration where this happens (see
[Quickstart](quickstart.md) for the log shape). The one-time `Initialize`
setup turn is NOT logged — it is a session-setup handshake, not an incoming
message — but every email-driven turn is. The git demo beat is the moment
the showcase is built around; the logs make it observable.

### Error surfacing in the reply

The agent's workflow phase that runs the commit+push also captures any error
encountered during the write/commit/push and surfaces it in the reply (it
does not swallow it). If the commit fails — for example, because the
configured git remote is unreachable, or because `yoker:git`'s permissions
disallow push to the configured remote — the reply body reports the failure
rather than reporting success. The owner sees the failure in the reply
email and can fix the configuration. This is part of the bounded-tool
contract: the agent is honest about what it did and what it did not do,
because the reply is the only channel the owner has to verify the agent's
actions. A silent failure would be the worst outcome; the agent definition
explicitly forbids it.

## 11. Recipient safety

Reply safety is a `simple-email-gw` config option, not package code. The
loop refuses to start if the whitelist is disabled — the whitelist fails
open, so an unset whitelist would let the assistant reply to arbitrary
senders. The C1 blocking fix in `loop.py` raises `RuntimeError` before
constructing the `Agent`:

```python
if not get_recipient_whitelist().enabled:
    raise RuntimeError(
      "Recipient whitelist is disabled — refusing to run (fails open). "
      "Set EMAIL_RECIPIENT_DOMAINS, EMAIL_RECIPIENT_ADDRESSES, "
      "or EMAIL_RECIPIENT_WHITELIST_JSON to enable outgoing reply safety."
    )
```

Set the whitelist to the single owner address in `.env`:

```
EMAIL_RECIPIENT_WHITELIST_ADDRESSES=owner@example.com
```

Leaving it broad lets the agent reply to arbitrary senders. The whitelist is
silently disabled if unset or wrong — the env var name is
`EMAIL_RECIPIENT_WHITELIST_ADDRESSES` (NOT `EMAIL_RECIPIENT_ADDRESSES`); the
wrong name silently disables the whitelist. This is a `simple-email-gw`
config concern, not package code — Python relies on the gateway's existing
config; no package-level allowlist code is written. See [Security](security.md)
for the full discussion and the upstream bug filed against `simple-email-gw`'s
own README.

## 12. Out of scope (first pass)

The first pass is deliberately small. These are explicitly deferred and
tracked in `TODO.md` under "Unsorted":

- **HTML styling polish** — the first pass ships unstyled HTML from the
  `md_to_html` tool. CSS, inline styles, dark-mode friendliness are a later
  polish task.
- **Attachment handling** — explicitly out of scope. The `fetch_message`
  result includes attachment metadata but Python ignores it.
- **Batch per-iteration processing** — first pass is one email per
  iteration; batching is a later optimization.
- **Multi-account email support** — out of scope; single account (`"default"`).
- **A `make run-demo` target** — a target that seeds a local mailbox and
  runs one iteration end-to-end for showcase purposes. Nice to have; not in
  the first pass.
- **Phase B bounded tools** — the only new bounded tool in scope for the
  first pass is `md_to_html` (the showcase's "create your own bounded tool"
  example). All other new bounded tools remain Phase B.

The first pass satisfies the project's stated scope: port the agent +
skills, remove MCP email logic, wrap in the Python email loop, demonstrate
yoker-as-SDK with a curated tool set, and demonstrate BOTH halves of
yoker's tool model — using built-in curated tools AND authoring a custom
local tool (the `md_to_html` converter). What is out of scope is documented
here and in `TODO.md`; everything else is in.

---

This is the end of the narrative. The supporting pages hold the long-form
reference: [Architecture](architecture.md) for the seam-by-seam detail,
[Porting Map](porting-map.md) for the full per-element table,
[Security](security.md) for the security configuration and the manifest
review process, [Configuration](configuration.md) for the full `~/.yoker.toml`
and `.env` reference, and [API](api.md) for the public API surface.