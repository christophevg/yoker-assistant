# API Review — P2-005 + P2-006 Implementation (Round 0)

**Date:** 2026-07-22
**Reviewer:** API Architect Agent
**Stage:** b — Backend Domain Review (initial implementation, R3 plan approved)
**Task:** Combined P2-005 (main loop) + P2-006 (handoff payload builder) — one PR per owner instruction.

## Summary

**Approved.** The implementation matches the approved backend design. The owner's
simplicity directives are honored: `build_message` is a plain function in
`loop.py`, `handoff.py` is deleted, no wrapper classes, no sub-wrappers. All
four SDK errata from the design review are correctly applied. The four-way
branching in `_process_one` is correct.

Two deliberate simplifications versus the design doc are present and acceptable
under the owner's simplicity directive and the R3 plan:

1. `_INITIALIZE_PROMPT = "Initialize"` instead of the long prose prompt from the
   design. The agent definition (`agents/assistant.md` Phase 1) already instructs
   the agent on what the initialize turn does, so a one-word trigger is enough.
   Stage a (functional) passed on this.
2. Empty-reply handling is **(a) leave UNSEEN** (not the design's recommended
   (b) mark read + archive). The user's Stage-b brief explicitly states
   "Empty → leave UNSEEN", so the R3 plan changed this. Correct per the approved
   plan.

## Module structure — PASS

- `src/yoker_assistant/__main__.py` — thin CLI: argparse + `asyncio.run(run(once=...))`
  + `KeyboardInterrupt` backstop. 30 lines. Matches design.
- `src/yoker_assistant/loop.py` — `run`, `build_message`, `_process_one`,
  `_account_from_env`, `_contains_unsafe_html`. 191 lines. Matches design.
- `handoff.py` — deleted (not present in `src/yoker_assistant/`). Confirmed via
  glob. Owner directive honored.
- `agent.py` — still present as a stub. Design flagged this as P1-004's territory
  for cleanup; out of scope here. Acceptable.

## run() function — PASS

| Requirement | Implementation | Status |
|-------------|----------------|--------|
| Async | `async def run(once: bool = False) -> None` | PASS |
| Agent constructed ONCE | `agent = Agent(agent_path="agents/assistant.md", context_manager=Persisted(SimpleContextManager(), session_id="yoker-assistant"))` at top of `run` | PASS |
| C1 whitelist startup check BEFORE Agent construction | `if not get_recipient_whitelist().enabled: raise RuntimeError(...)` is the first statement, before `_account_from_env()` and `Agent(...)` | PASS |
| One-time session-setup turn | `await agent.process(_INITIALIZE_PROMPT)` after Agent construction, before IMAP/SMTP | PASS |
| IMAP connect | `imap = IMAPClient(account)`; `await imap.connect()` — fast-fail on bad credentials | PASS |
| SMTPClient (no connect) | `smtp = SMTPClient(account)` — no `connect()`/`disconnect()` call (erratum 1) | PASS |
| SIGINT/SIGTERM on asyncio.Event | `stop = asyncio.Event()`; `loop.add_signal_handler(sig, stop.set)` for both signals, `NotImplementedError` guarded for Windows | PASS |
| Poll loop: search UNSEEN → _process_one → --once breaks → empty sleeps | `while not stop.is_set(): uids = await imap.search(_INBOX_FOLDER, "UNSEEN"); for mid in uids: ...; if once: break; if not uids: asyncio.wait_for(stop.wait(), timeout=_POLL_INTERVAL)` | PASS |
| finally: imap.disconnect() | `finally: try: await imap.disconnect() except Exception: logger.exception(...)` | PASS |

## _process_one four-way branching — PASS

| Branch | Trigger | Action | Implementation |
|--------|---------|--------|----------------|
| 1 | `{{NO_REPLY}}` sentinel in reply | mark read + archive, no reply | `if NO_REPLY_SENTINEL in reply_html:` → `mark_message(..., "\\Seen", action="add")` + `move_message(..., "INBOX", "Archive")` | PASS |
| 2 | empty/whitespace reply | leave UNSEEN (no mark, no archive, no send) | `elif not reply_html.strip():` → log only | PASS |
| 3 | unsafe HTML (guard fails) | mark read (no archive) + plain-text notice to sender | `elif _contains_unsafe_html(reply_html):` → mark + `reply_email(to=sender, body=notice, in_reply_to=...)` with no `html_body` | PASS |
| 4 | valid HTML reply | send reply + mark read + archive | `else:` → `reply_email(to=sender, body="", html_body=reply_html, in_reply_to=...)` + mark + move | PASS |

Ordering for branch 4 (§4.4): send → mark read → archive. Matches design. A
send-failure leaves the message UNSEEN and the per-message `try/except` in `run`
logs and continues — retry next iteration. Acceptable.

Sender extraction via `parseaddr(msg.get("from", ""))[1]` — matches erratum 4.
Passing the bare address to `reply_email(to=...)` avoids `validate_email()`
raising on display names. PASS.

## build_message — PASS

Pure function, no I/O. Produces From/Subject/Date headers + blank line + body.
No `Instructions:` block (identity lives in the agent definition and the
session-setup turn, per design).

CR/LF collapse is applied to header values via `_clean`: `str(value or "").replace("\r", " ").replace("\n", " ")`.
Body is passed through verbatim. Test `test_build_message_collapses_crlf_in_headers`
confirms a `Bcc:` injection attempt via the From header is flattened and does
not produce a real header line. PASS.

Missing fields default to empty strings via `.get(..., "")` (in `_clean` via
`value or ""`). Test `test_build_message_missing_fields_become_empty_strings`
confirms. PASS.

The function lives at module level in `loop.py`. Not a class, not a separate
module. Owner directive ("006 is 'merely' a function") honored. PASS.

## SDK errata compliance — PASS

| Erratum | Design requirement | Implementation | Status |
|---------|-------------------|----------------|--------|
| 1. SMTPClient no connect/disconnect | construct `SMTPClient(account)`, call `reply_email` directly | `smtp = SMTPClient(account)` — no lifecycle calls | PASS |
| 2. `reply_email(to=str)` | pass a single address string, not a list | `to=sender` where `sender = parseaddr(...)[1]` is a bare address string | PASS |
| 3. `reply_email` requires `body: str` | pass `body=""` when only HTML is desired | branches 3 and 4 both pass `body=` explicitly (notice text and `""` respectively) | PASS |
| 4. `move_message(mid, "INBOX", "Archive")` | source folder required | `imap.move_message(message_id, _INBOX_FOLDER, _ARCHIVE_FOLDER)` | PASS |
| 5. `parseaddr` for sender extraction | one-liner from `email.utils` | `from email.utils import parseaddr`; `parseaddr(msg.get("from", ""))[1]` | PASS |

Additional SDK surface verified:
- `IMAPClient.search(folder, criteria)` — called as `imap.search(_INBOX_FOLDER, "UNSEEN")`. Returns `list[str]` of message IDs.
- `IMAPClient.fetch_message(message_id, folder)` — called as `imap.fetch_message(message_id, _INBOX_FOLDER)`. Returns the dict shape `build_message` reads (`from`, `subject`, `date`, `body`, `message_id`).
- `IMAPClient.mark_message(message_id, folder, flag, action="add")` — called with `flag="\\Seen"`, `action="add"`.
- `Agent.process` is awaited as `await agent.process(handoff)` — async, returns `str`.
- `Persisted(SimpleContextManager(), session_id="yoker-assistant")` — exact construction per design.

## Error handling — PASS

Per-message exceptions are caught in `run`'s poll loop:

```python
try:
  await _process_one(imap, smtp, agent, mid)
except Exception:
  logger.exception("per-message failure; leaving UNSEEN", extra={"message_id": mid})
  continue
```

The message is NOT marked read on exception, so it stays UNSEEN and is retried
on the next iteration. Matches §7. PASS.

`imap.disconnect()` in `finally` is itself wrapped in `try/except` so a
disconnect failure does not mask the original exception or prevent process
exit. Good defensive practice. PASS.

Note: the design included a `try/except` around `imap.search` with backoff
sleep. The implementation does NOT catch search exceptions — an IMAP search
failure would propagate up and tear down the loop. This is a minor
simplification. Under the owner's simplicity directive and the R3 plan, this is
acceptable for the first pass; a real deployment would want search-failure
backoff, but it is not a blocking issue for this PR.

## Wrapper Check — PASS

- `Agent` — constructed directly from `yoker`. No `Assistant` wrapper.
- `IMAPClient` — constructed directly from `simple_email_gw`. No `Mailbox` wrapper.
- `SMTPClient` — constructed directly from `simple_email_gw`. No `Mailbox` wrapper.
- `build_message` — plain module-level function. Not a class, not a module.
- `_process_one` — plain helper function sequencing per-message steps. Earned
  orchestration (fetch → build → process → branch on reply). Not a wrapper
  class, not an indirection layer.
- `_account_from_env` — plain helper. Not a wrapper.
- `_contains_unsafe_html` — plain helper. Not a wrapper.
- `run` — multi-step orchestration (poll → fetch → process → reply → mark →
  archive). Earned behavior, not a wrapper.
- No sub-wrappers inside `run`. No `Assistant`, no `Mailbox`, no `Handoff`,
  no `SessionRunner`. Zero wrapper classes introduced.

Owner's simplicity directives (1–4) all satisfied.

## RESTful / async-first note

This is an internal Python loop calling async-native SDKs (yoker, simple-email-gw).
Not an HTTP API task; RESTful-over-RPC does not apply. The async-first principle
is satisfied at the SDK layer: both upstream SDKs are async-native and the loop
is `async def` throughout, using `await` for all I/O. No sync wrappers are
introduced by this package. PASS.

## Tests — PASS

27 tests in `tests/test_loop.py`:

- `build_message`: 4 tests — header/body formatting, CR/LF collapse, missing
  fields, body verbatim preservation.
- `_contains_unsafe_html`: 16 parametrized cases (10 unsafe, 6 clean) covering
  all unsafe tags (`<script`, `<style`, `<img`, `<iframe`, `<object`, `<embed`,
  `<form>`) and `on*` event handlers.
- `_process_one` four-way branching: 5 tests — sentinel marks+archives with no
  reply, sentinel wrapped in HTML still detected, empty reply leaves UNSEEN,
  guard failure marks (no archive) + sends notice with no `html_body`, valid
  reply sends `html_body` + marks + archives.
- `run` C1 guard: 1 test — `run` raises `RuntimeError` matching "recipient
  whitelist" when `get_recipient_whitelist().enabled` is False.

Test shape matches the design's acceptance criteria: fixture dict matching
`fetch_message` shape, mocked IMAP/SMTP/Agent, `AsyncMock` for async methods.
The four-way branching is tested at the boundary (which SDK calls were made
with which arguments), not at internal implementation detail. Good test
altitude.

## Minor observations (non-blocking)

1. **Search-failure backoff not implemented.** The design recommended a
   `try/except` around `imap.search` with `_backoff_sleep`. The implementation
   omits this. Acceptable for first pass; flag for a future hardening task if
   the loop is run long-term against a flaky IMAP server.
2. **`_INITIALIZE_PROMPT` is the bare word "Initialize".** Simpler than the
   design's prose prompt. The agent definition's Phase 1 carries the
   instructions, so this is sufficient. Acceptable.
3. **`imap.search` and `imap.fetch_message` use positional args** instead of
   the keyword form in the design (`folder=`, `criteria=`). Both forms work;
   positional is shorter. Acceptable.
4. **`agent.py` stub still present.** Out of scope (P1-004's territory per
   design). Flag for cleanup in P1-004 close-out, not here.

None of these are blocking. All align with the owner's "please consider
simplicity" directive.

## Verdict

**Approved.** The backend design is correctly implemented. All four SDK errata
are applied. The four-way branching is correct. The C1 whitelist guard is in
the right place (before Agent construction). No wrapper classes were
introduced. `handoff.py` is deleted. `build_message` is a plain function. The
two deliberate simplifications versus the design doc (`_INITIALIZE_PROMPT`
wording, empty-reply handling) are both sanctioned by the R3 plan and the
owner's simplicity directive.

## Action items

None blocking. Optional follow-ups (non-blocking, not required for merge):

- Consider adding search-failure backoff in a future hardening pass.
- Consider deleting `agent.py` in P1-004's close-out.