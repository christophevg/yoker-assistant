# API Review — P2-005 + P2-006 (Main loop + handoff payload builder)

**Date:** 2026-07-22
**Reviewer:** API Architect Agent
**Task:** Combined review of P2-005 (main loop) and P2-006 (handoff payload builder),
folded into one PR per owner instruction.
**Owner instruction quoted:**
> "Combine P2-005 and P2-006 into one PR, because 006 is 'merely' a function,
> so don't make it any bigger than that. I think the split handoff-builder still
> is a residu from an overengineered previous design. So please consider
> simplicity when implementing these two in one go."

## Summary

The combined task is approved with a small set of required spec errata fixes.
The owner's simplicity directive is honored: `build_message` is a plain function
in the loop module, not a separate `handoff.py`. No wrapper classes are
introduced. The loop is multi-step orchestration (earned behavior) and calls
`Agent`, `IMAPClient`, `SMTPClient`, and `build_message` directly.

Three spec/implementation mismatches must be corrected against the
functional.md / TODO spec text (all are errata in the spec, not in the owner's
intent):

1. `SMTPClient` has NO `connect()`/`disconnect()` methods — it is fire-and-forget
   per send via `aiosmtplib.send`. The spec text in functional.md §2.4 and
   TODO P2-005 that says `smtp.connect()`/`smtp.disconnect()` is inaccurate.
2. `SMTPClient.reply_email` takes `to: str` (a single address string), NOT
   `to=[sender]` (a list) as shown in functional.md §2.4. TODO P2-005 is correct.
3. `SMTPClient.reply_email` REQUIRES a `body: str` argument (plain text). The
   spec only mentions `html_body=`. The loop must pass `body=""` explicitly.

One open decision flagged for the owner: how to handle an empty agent reply
(see §Empty-reply handling below).

## SDK findings

### yoker SDK (confirmed against `/Users/xtof/Workspace/agentic/yoker/src/yoker`)

- `from yoker import Agent, Persisted, SimpleContextManager` — all exported
  from the top-level package (`yoker/__init__.py`).
- `Agent.__init__(config=None, thinking_mode=..., agent_definition=None,
  agent_path=None, context_manager=None, plugins=(), backend=None,
  parse_cli_args=False, console_logging=True)`. The TODO construction
  `Agent(agent_path="agents/assistant.md",
  context_manager=Persisted(SimpleContextManager(), session_id="yoker-assistant"))`
  is valid.
- `async def Agent.process(message: str) -> str` — async, returns the agent's
  final text response. Concurrent calls are serialized internally via a queue;
  the loop is single-threaded so this is moot but harmless.
- `Persisted(wrapped, storage_path=None, session_id="auto")` — JSONL persistence
  wrapper. `Persisted(SimpleContextManager(), session_id="yoker-assistant")` is
  the documented usage pattern. Default storage path is
  `~/.cache/yoker/sessions`.
- `Agent` construction triggers `load_dotenv(.env)`, `load_dotenv(.env.local)`,
  config discovery from `./yoker.toml` then `~/.yoker.toml`, plugin loading,
  skill loading, and tool filtering. This is heavy but happens ONCE at startup,
  not per email — matches the design.
- No `Assistant` wrapper class exists or is needed (P1-004 decision). The loop
  constructs `Agent` directly.

### simple-email-gw SDK (confirmed against
`/Users/xtof/Workspace/agentic/simple-email-gw/src/simple_email_gw`)

- `from simple_email_gw import EmailAccount, IMAPClient, SMTPClient`.
- `EmailAccount(name, imap_host, imap_port=993, smtp_host, smtp_port=587,
  username, password, ...)` — pydantic model. `imap_port`/`smtp_port` have
  defaults; `name`, `imap_host`, `smtp_host`, `username`, `password` are
  required.
- `IMAPClient(account)` — has explicit `async def connect()` and
  `async def disconnect()`. The connection is also lazily re-established by
  `search`/`fetch_message`/`mark_message`/`move_message` via internal
  `await self.connect()`, so an explicit `await imap.connect()` at startup is
  optional but matches the spec and gives fast-fail on bad credentials.
- `IMAPClient.search(folder="INBOX", criteria="ALL", limit=50) -> list[str]` —
  returns message ID strings. `criteria="UNSEEN"` works (validated against
  `IMAP_CRITERIA_PATTERN`).
- `IMAPClient.fetch_message(message_id, folder="INBOX") -> dict[str, Any]` —
  returns the raw message dict. **Confirmed dict shape:**
  `id`, `folder`, `subject`, `from`, `to`, `date`, `body`, `attachments`,
  `read`, `message_id`, `references`. This is the shared contract
  `build_message` reads from. `from` is the full From header (may include a
  display name like `"Name <addr@domain>"`); `message_id` is the raw
  `Message-ID` header value including angle brackets.
- `IMAPClient.mark_message(message_id, folder, flag, action="add") -> bool` —
  flag is e.g. `"\\Seen"`, action is `"add"` or `"remove"`.
- `IMAPClient.move_message(message_id, source_folder, dest_folder) -> bool` —
  NOTE: requires the source folder argument. The TODO abbreviated this as
  `move_message(..., "Archive")`; the actual call is
  `move_message(mid, "INBOX", "Archive")`.
- **`SMTPClient(account)` has NO `connect()`/`disconnect()` methods.** It uses
  `aiosmtplib.send()` per call, which connects, sends, and tears down each
  time. The loop must NOT call `await smtp.connect()` — it will raise
  `AttributeError`. Just construct and call `reply_email`.
- `SMTPClient.reply_email(to, subject, body, in_reply_to, references=None,
  html_body=None, append_to_sent=False, append_folder=None,
  imap_client=None)` — **`to: str` (single address string, NOT a list)**,
  **`body: str` is required** (no default), `html_body: str | None` is optional.
  The loop must pass `body=""` when only HTML is desired. The plain-text
  alternative will be empty; accessibility polish is deferred per §4.3.
  Recipient whitelist (`EMAIL_RECIPIENT_ADDRESSES`) is enforced by the gateway,
  not the loop.
- `reply_email` validates `to` with `validate_email()`, which expects a bare
  address. The loop must extract the address from `msg["from"]` using
  `email.utils.parseaddr(msg["from"])[1]` — a one-liner. Passing the raw
  `msg["from"]` (with a display name) will raise `ValueError`.

## Module structure recommendation

**Recommended: `__main__.py` (thin entry point) + `loop.py` (loop + build_message).
Delete `handoff.py`.**

Rationale:

- The owner's instruction is that `build_message` is a function, not a module.
  Both options below satisfy that. The choice is only about where the loop
  itself lives.
- Option A (`__main__.py` only, ~150 lines): one file, simplest. Acceptable.
- Option B (recommended): `__main__.py` stays the thin CLI wrapper
  (argparse + `asyncio.run(run(once=...))` + signal setup), `loop.py` holds
  `run()`, `build_message()`, and `_INITIALIZE_PROMPT`. The
  `__init__.py` already references `loop` as a module; the stub already
  exists; `pyproject.toml` already wires `yoker-assistant =
  "yoker_assistant.__main__:main"`. Keeping `__main__.py` thin is the standard
  Python pattern and makes `run`/`build_message` importable for unit tests
  without touching the `if __name__ == "__main__"` path.
- `handoff.py` is residue from the overengineered design per the owner. Delete
  it. Its stub is only 4 lines.
- `agent.py` is also a stub residue from the overengineered `Assistant`-wrapper
  design (P1-004 descoped the wrapper). It is out of scope for this task
  (P1-004's territory) but flag it for cleanup: the loop constructs `Agent`
  directly and does not import `agent.py`. Recommend deleting `agent.py` in a
  follow-up or in P1-004's close-out, not in this PR.

## build_message function design

Lives in `loop.py`. Pure function, no I/O, no instructions block. Accepts the
raw `simple_email_gw` message dict per P2-006's post-P1-003 scope update.

```python
def build_message(msg: dict[str, Any]) -> str:
  """Build the per-email handoff payload (§4.1 format).

  From/Subject/Date headers + body only. NO instructions block — identity
  lives in the agent definition and the one-time session-setup step.
  Reads the raw simple_email_gw fetch_message dict directly (P1-003 descoped
  the EmailMessage dataclass).
  """
  return (
    f"From: {msg.get('from', '')}\n"
    f"Subject: {msg.get('subject', '')}\n"
    f"Date: {msg.get('date', '')}\n"
    f"\n"
    f"{msg.get('body', '')}"
  )
```

Notes:

- Uses `.get(..., "")` so a missing field does not crash the loop; the §4.1
  format is still produced. `fetch_message` always populates these keys when
  the raw message parses, so this is defensive only.
- The output matches §4.1 exactly: three header lines, a blank line, then the
  body. No `Instructions:` block. No trailing newline beyond what the body
  already contains.
- Unit-testable with a fixture dict matching `fetch_message`'s shape, per the
  P2-006 acceptance criterion.

## run() function design

Lives in `loop.py`. Async. Construct everything ONCE, run the poll loop,
graceful shutdown.

```python
import asyncio, logging, os, signal
from email.utils import parseaddr
from typing import Any
from yoker import Agent, Persisted, SimpleContextManager
from simple_email_gw import EmailAccount, IMAPClient, SMTPClient

logger = logging.getLogger(__name__)

_INITIALIZE_PROMPT = (
  "Initialize this session. Read PERSONAL.md via yoker:read to load the "
  "owner's identity, tone, and learned behaviours. Confirm readiness to "
  "process incoming emails. Do not reply to any email yet — this is the "
  "session-setup turn only."
)

_POLL_INTERVAL = float(os.environ.get("YOKER_POLL_INTERVAL", "60"))
_ARCHIVE_FOLDER = os.environ.get("YOKER_ARCHIVE_FOLDER", "Archive")
_INBOX_FOLDER = os.environ.get("YOKER_INBOX_FOLDER", "INBOX")


def _account_from_env() -> EmailAccount:
  return EmailAccount(
    name="default",
    imap_host=os.environ["EMAIL_IMAP_HOST"],
    imap_port=int(os.environ.get("EMAIL_IMAP_PORT", "993")),
    smtp_host=os.environ["EMAIL_SMTP_HOST"],
    smtp_port=int(os.environ.get("EMAIL_SMTP_PORT", "587")),
    username=os.environ["EMAIL_USERNAME"],
    password=os.environ["EMAIL_PASSWORD"],
  )


async def run(once: bool = False) -> None:
  account = _account_from_env()
  agent = Agent(
    agent_path="agents/assistant.md",
    context_manager=Persisted(SimpleContextManager(), session_id="yoker-assistant"),
  )
  # One-time session-setup turn (§4.1). The agent reads PERSONAL.md and
  # initializes identity on this first turn, before any email is delivered.
  await agent.process(_INITIALIZE_PROMPT)

  imap = IMAPClient(account)
  await imap.connect()  # fast-fail on bad credentials
  smtp = SMTPClient(account)  # no connect/disconnect — fire-and-forget per send

  stop = asyncio.Event()

  def _on_signal() -> None:
    stop.set()
  loop = asyncio.get_running_loop()
  for sig in (signal.SIGINT, signal.SIGTERM):
    try:
      loop.add_signal_handler(sig, _on_signal)
    except NotImplementedError:
      pass  # Windows

  try:
    while not stop.is_set():
      try:
        ids = await imap.search(folder=_INBOX_FOLDER, criteria="UNSEEN")
      except Exception:
        logger.exception("IMAP search failed; backing off")
        await _backoff_sleep(stop, _POLL_INTERVAL)
        if once:
          break
        continue

      for mid in ids:
        if stop.is_set():
          break
        try:
          await _process_one(imap, smtp, agent, mid)
        except Exception:
          logger.exception("per-message failure; leaving UNSEEN", message_id=mid)
          # §7: skip and continue — message stays UNSEEN and retries next iteration

      if once:
        break
      if not ids:
        await _backoff_sleep(stop, _POLL_INTERVAL)
  finally:
    try:
      await imap.disconnect()
    except Exception:
      logger.exception("imap disconnect failed")


async def _process_one(imap, smtp, agent, mid: str) -> None:
  msg = await imap.fetch_message(mid, folder=_INBOX_FOLDER)
  message = build_message(msg)
  reply_html = await agent.process(message)
  if reply_html and reply_html.strip():
    sender = parseaddr(msg.get("from", ""))[1]
    subject = msg.get("subject", "")
    await smtp.reply_email(
      to=sender,
      subject=f"Re: {subject}",
      body="",  # plain-text alternative intentionally empty (§4.3)
      html_body=reply_html,
      in_reply_to=msg.get("message_id", ""),
    )
    # §4.4 ordering: send → mark read → archive. Mark read immediately after
    # a successful send so a partial failure does not duplicate the reply.
    await imap.mark_message(mid, _INBOX_FOLDER, "\\Seen", "add")
    await imap.move_message(mid, _INBOX_FOLDER, _ARCHIVE_FOLDER)
  else:
    # Empty-reply handling — see §Empty-reply handling below.
    # Decision: mark read + archive. Treat as "agent chose not to reply";
    # avoid retrying forever.
    logger.info("agent returned empty reply; marking read and archiving", message_id=mid)
    await imap.mark_message(mid, _INBOX_FOLDER, "\\Seen", "add")
    await imap.move_message(mid, _INBOX_FOLDER, _ARCHIVE_FOLDER)


async def _backoff_sleep(stop: asyncio.Event, seconds: float) -> None:
  try:
    await asyncio.wait_for(asyncio.create_task(stop.wait()), timeout=seconds)
  except asyncio.TimeoutError:
    pass
```

Notes / decisions:

- **`_process_one` extracted as a helper** — this is NOT a wrapper class, just
  a function that sequences the per-message steps. It keeps `run` readable and
  gives the per-message `try/except` a clean boundary. If the owner prefers
  inlining, it can be inlined; the behavior is identical. Flag this as a minor
  structural choice, not a deviation from the simplicity principle.
- **No SMTP lifecycle calls** — `SMTPClient` has no `connect()`/`disconnect()`.
  This is the central spec erratum; see §Spec errata below.
- **Sender extraction** — `parseaddr(msg["from"])[1]` is a one-liner from the
  stdlib `email.utils`. Passing the raw `msg["from"]` to `reply_email(to=...)`
  would raise `ValueError` from `validate_email()` when a display name is
  present.
- **`body=""`** — required by `reply_email`'s signature. The spec only
  mentions `html_body=`; the loop passes an empty plain-text alternative per
  §4.3's "intentionally empty in the first pass".
- **Ordering (§4.4)** — send → mark read → archive. If send fails, the
  `except` in `run` catches it, leaves the message UNSEEN, and continues. If
  mark_read fails after a successful send, the message is still UNSEEN and
  will be reprocessed (duplicate reply risk accepted per §4.4). If archive
  fails after mark_read, the message is already `\Seen` so it will NOT be
  reprocessed; it lingers in INBOX until the next loop tidies it. Accepted.
- **`--once` flag** — implemented as a `once: bool` parameter to `run()`. The
  loop runs one search iteration (processing all currently-unseen messages in
  that one iteration), then breaks. `__main__.py` parses `--once` and calls
  `asyncio.run(run(once=args.once))`. An empty inbox with `--once` exits
  cleanly (the `if once: break` after an empty `ids` list).
- **Graceful shutdown** — `SIGINT`/`SIGTERM` set an `asyncio.Event`. The
  signal handler is a no-op on Windows (guarded by
  `NotImplementedError`). The poll loop checks `stop.is_set()` between
  messages and breaks. The in-flight message completes (the per-message
  `try/except` does not check `stop`). `imap.disconnect()` runs in `finally`.
  Exit code 0 via `__main__.py` returning normally.
- **Connection failure backoff** — on `imap.search` exception, log, sleep
  `_POLL_INTERVAL`, continue. A real exponential backoff is out of scope for
  the first pass; the spec says "e.g. double the interval up to a cap" but a
  fixed interval is acceptable for the demo. Flag as a possible enhancement.
- **No `--poll-interval` CLI flag** — the interval is env-driven
  (`YOKER_POLL_INTERVAL`). If the owner wants a CLI flag, add it; not required
  by the spec.

## __main__.py design (thin entry point)

```python
import argparse, asyncio, sys

from yoker_assistant.loop import run


def main() -> None:
  parser = argparse.ArgumentParser(prog="yoker-assistant")
  parser.add_argument("--once", action="store_true",
                      help="process one poll iteration and exit")
  args = parser.parse_args()
  try:
    asyncio.run(run(once=args.once))
  except KeyboardInterrupt:
    sys.exit(0)


if __name__ == "__main__":
  main()
```

Notes:

- `KeyboardInterrupt` is a belt-and-suspenders backstop; the `asyncio.Event`
  signal handler is the primary path. `SIGINT` normally triggers the event
  handler, but if it fires before the loop installs the handler (e.g. during
  `Agent` construction), `KeyboardInterrupt` still exits cleanly.
- `asyncio.run()` owns the event loop lifecycle. Signal handlers are installed
  inside `run()` via `asyncio.get_running_loop()`.

## Spec errata to correct in functional.md / TODO

These are inaccuracies in the spec text, not in the owner's intent. The
implementation must follow the SDK's actual signatures, not the spec text.

1. **`SMTPClient` has no `connect()`/`disconnect()`.** functional.md §2.4
   shows `await smtp.connect()` / `await smtp.disconnect()` in a `try/finally`
   block. TODO P2-005 says "smtp.connect()/smtp.disconnect() around the send
   (or once for the loop's lifetime — implementation choice)". Neither is
   possible: `SMTPClient` uses `aiosmtplib.send()` per call and has no
   connection lifecycle methods. **Action:** remove the `smtp.connect()`/
   `smtp.disconnect()` lines from §2.4's example and the "implementation
   choice" clause from TODO P2-005. The loop constructs `SMTPClient(account)`
   and calls `reply_email(...)` directly.
2. **`reply_email(to=...)` takes a `str`, not a list.** functional.md §2.4
   shows `to=[sender]`. The actual signature is `to: str`. TODO P2-005's
   `to=sender` is correct. **Action:** fix §2.4's example to `to=sender`.
3. **`reply_email` requires `body: str`.** Neither §2.4 nor §4.3 mentions
   passing `body=""`. The actual signature has `body` as a required
   positional/keyword argument with no default. **Action:** note in §4.3 that
   the loop passes `body=""` (plain-text alternative intentionally empty in
   the first pass).
4. **`move_message` requires the source folder.** TODO P2-005 abbreviates as
   `imap.move_message(..., "Archive")`. The actual signature is
   `move_message(message_id, source_folder, dest_folder)`. **Action:** the
   implementation calls `imap.move_message(mid, "INBOX", "Archive")`; update
   the TODO example for clarity.

## Empty-reply handling (decision flagged for owner)

§4.3 says: "if the agent returns no content, the loop skips the send (and the
message-handling decision in that case is a loop concern)". §7 says: "Unexpected
exception per message: log, skip the message (leave it UNSEEN so it is
retried), continue the loop." An empty reply is NOT an exception — it is a
successful agent turn that produced no content. Three options:

| Option | Behavior | Risk |
|--------|----------|------|
| (a) Leave UNSEEN | retries every iteration | infinite loop if agent consistently returns empty |
| (b) Mark read + archive | treats as "handled, no reply" | silences messages the agent declined to reply to |
| (c) Mark read, don't archive | visible in INBOX, not retried | lingers, requires manual tidy |

**Recommended: (b) mark read + archive.** This treats an empty reply as "the
agent chose not to reply" and avoids an infinite retry loop on a message the
agent cannot handle. It is the simplest deterministic behavior. The
implementation above uses (b).

**This is a loop concern the spec explicitly leaves open.** Confirm with the
owner before merging. If the owner prefers (a) or (c), the change is two lines
in `_process_one`'s `else` branch.

## Wrapper Check

PASS.

- `Agent` — constructed directly from `yoker`. No `Assistant` wrapper (P1-004).
- `IMAPClient` — constructed directly from `simple_email_gw`. No `Mailbox`
  wrapper (P1-003 descoped it).
- `SMTPClient` — constructed directly from `simple_email_gw`. No `Mailbox`
  wrapper.
- `build_message` — a plain module-level function in `loop.py`. NOT a class,
  NOT a separate module (`handoff.py` deleted per owner instruction).
- `_process_one`, `_account_from_env`, `_backoff_sleep` — plain helper
  functions. NOT wrapper classes. `_process_one` sequences the per-message
  steps (earned orchestration, factored for readability); it introduces no
  indirection layer.
- The loop itself (`run`) is multi-step orchestration
  (poll → fetch → process → reply → mark → archive). That IS earned behavior,
  not a wrapper. No sub-wrappers inside it.

## RESTful / API design note

This task is not an HTTP API task — it is an internal Python loop calling SDK
libraries. The RESTful-over-RPC principle does not apply. The async-first
principle applies to the SDKs (yoker and simple-email-gw are both async-native
and the loop is async); both SDKs already provide async-primary APIs, so the
loop uses `AsyncClient`-equivalent surfaces directly. No sync wrappers are
introduced by this package.

## Action items

1. **Implement `loop.py`** with `build_message`, `run`, `_INITIALIZE_PROMPT`,
   and the helpers above.
2. **Implement `__main__.py`** as the thin argparse + `asyncio.run` wrapper.
3. **Delete `handoff.py`** (residue from overengineered design per owner).
4. **Update `__init__.py` docstring** — it currently says "Those live in
   `__main__`, `loop`, and `agent`." After this PR, `handoff` is gone. `agent`
   is still a stub (P1-004's territory); leave the `agent` reference or remove
   it in P1-004's close-out.
5. **Fix spec errata** in `analysis/functional.md` §2.4 and §4.3 and in
   `TODO.md` P2-005 (the four items in §Spec errata above). These can be done
   in the same PR or a follow-up docs commit.
6. **Confirm empty-reply handling** with the owner (option (b) recommended).
7. **Add unit tests** for `build_message` (fixture dict matching
   `fetch_message` shape) and for `run(once=True)` on an empty inbox (mock
   IMAP/SMTP/Agent).
8. **Flag `agent.py` for cleanup** in P1-004's close-out — it is a stub residue
   from the descoped `Assistant` wrapper.

## Verdict

**Approved** with required spec errata corrections (§Spec errata above) and
the empty-reply decision flagged for owner confirmation. The implementation
matches the owner's simplicity directive: `build_message` is a function in
`loop.py`, no `handoff.py`, no wrapper classes, no sub-wrappers. The three
SDK-signature mismatches (SMTP lifecycle, `to` type, required `body` arg) are
spec text errors that the implementation must ignore in favor of the actual
SDK signatures.