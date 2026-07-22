# Plan Revision R2 — Owner Feedback Round 2 on PR #7 (P2-005 + P2-006)

**Date:** 2026-07-22
**Author:** Functional Analyst
**Scope:** Incorporate owner feedback round 2 on PR #7 into the implementation
plan for the combined P2-005 + P2-006 task. This revises R1's guard-failure
branch and adds a notice-to-owner requirement.

## Owner's instructions (quoted verbatim)

> I agree with your guard-related approach. In that case, I think we should
> reply to the owner with a notice stating that the agent produced a reply
> that contained unsafe HTML. This should indeed happen rarely to never, so
> blocking and informing the owner about this is surely a good response.
>
> Let's assume we "fix" the agent - because it was a small bug - what happens
> with the "seen" but "not archived" email? Will it be reprocessed on the next
> iteration? Does the owner need to do something special to have it
> re-processed, like remove the "seen" flag?

## Does the revision satisfy each quoted item?

1. **"reply to the owner with a notice stating that the agent produced a reply
    that contained unsafe HTML."** YES. On guard failure, the loop sends a
   plain-text notice to the owner via `smtp.send_email(to=[account.username],
   ...)`. See §2.

2. **"blocking and informing the owner about this is surely a good response."**
   YES. The unsafe reply is blocked (never sent to the original sender). The
   owner is informed via the notice. See §2.

3. **"what happens with the 'seen' but 'not archived' email? Will it be
    reprocessed on the next iteration?"** ANSWERED. Under R1 (mark read + no
   archive), it would NOT be reprocessed — `search("INBOX", "UNSEEN")` skips
   `\Seen` messages, and the owner would have to manually remove the `\Seen`
   flag. R2 changes this: the message is left UNSEEN on guard failure, so it
   IS reprocessed automatically on the next iteration. See §1.

4. **"Does the owner need to do something special to have it re-processed,
    like remove the 'seen' flag?"** ANSWERED. Under R2, no — the loop does not
   mark the message read on guard failure, so no manual flag removal is needed.
   The message retries automatically. To STOP retries, the owner deletes the
   message or marks it read manually. See §1.

5. **"This should indeed happen rarely to never."** ACKNOWLEDGED. This
   expectation justifies the simple design: repeated-notice noise is a
   non-issue in practice, so no rate-limiting or "notify once" state is added.
   See §3 concern 1.

No deviations from the owner's proposals. The notice requirement is
implemented as stated. The reprocessing question is resolved in favor of the
owner's original "try again" framing (which R1 had deviated from for guard
failures). R2 reverts that deviation.

---

## 1. Reprocessing question — answer and recommended option

### 1.1 The SDK facts

Confirmed against `/Users/xtof/Workspace/agentic/simple-email-gw/src/simple_email_gw`:

- `IMAPClient.search(folder="INBOX", criteria="UNSEEN")` returns ONLY messages
  without the `\Seen` flag. This is the IMAP semantic; a `\Seen` message is
  invisible to the next poll.
- `IMAPClient.mark_message(message_id, folder, flag, action="add"|"remove")`
  can remove `\Seen` via `action="remove"`, `flag="\\Seen"`. So un-seeing is
  possible — but it requires an explicit extra call and is manual only if the
  owner wants to reprocess a seen message.
- `SMTPClient.send_email(to: list[str], subject, body, cc=None, bcc=None,
  html_body=None, ..., append_to_sent=False, ...)` exists and is the right
  primitive for a notice that is NOT a reply to the original sender. It takes
  a list of recipients (unlike `reply_email` which takes a single `to: str`).
- The owner's email address is `account.username` (the same address used as
  `From` in `send_email`). No new env var. `EmailAccount.username` is
  populated from `EMAIL_USERNAME`.

### 1.2 The three options

| Option | On guard failure | Reprocessed next iteration? | Owner action to reprocess? | Owner action to stop retries? |
|--------|------------------|------------------------------|-----------------------------|-------------------------------|
| A (R1) | Mark read, no archive | NO | Manually remove `\Seen` flag | (already stopped) |
| B (R2) | Leave UNSEEN, send notice | YES (automatic) | None | Delete message or mark read |
| C | Mark read, move to "Failed" | NO | Move back to INBOX as unread | (already stopped) |

### 1.3 Recommendation: Option B (leave UNSEEN, send notice)

Option B is the simplest option that:

- **Answers the owner's question directly:** "It will be reprocessed
  automatically on the next iteration. You do not need to remove the `\Seen`
  flag — the loop never sets it on guard failure."
- **Aligns with the owner's original "try again" framing for problems.** The
  owner's decision-2 in R1 was "a problem → try again" for empty replies.
  Guard failure IS a problem. R1 deviated from this framing for guard
  failures (marking read to avoid infinite loops). R2 reverts that deviation:
  the notice makes infinite retries visible rather than silent, and the poll
  interval bounds the rate. The owner can delete the message or fix the agent.
- **Does not strand messages.** A seen-but-not-archived message under R1 is
  stuck — invisible to the poll, requiring manual flag surgery. Under R2, the
  message stays in the normal retry flow until it either succeeds (agent
  fixed) or the owner intervenes.
- **Does not add complexity.** No new folders (Option C), no manual flag
  removal (Option A), no "notify once" state tracking. The message stays in
  its default UNSEEN state; the loop simply does less (no `mark_message` call
  on guard failure) and adds one `send_email` call (the notice).

### 1.4 Why R1's deviation is no longer justified

R1 marked read on guard failure to prevent "infinite retry on a persistent
prompt-injection payload." That justification assumed silent retries. With
the owner's new notice requirement (§2), retries are no longer silent — the
owner gets an email each time. The owner explicitly said this "should indeed
happen rarely to never," so repeated notices are a non-issue in practice and
a useful signal in the rare case they occur. The deviation's premise (silent
infinite loop) is gone; the deviation should be reverted.

### 1.5 Consistency with empty-reply handling

R2 makes guard-failure handling consistent with empty-reply handling (R1
branch 2): both leave the message UNSEEN and retry next iteration. The only
difference is that guard failure also sends a notice. This is simpler to
explain, simpler to test, and simpler to document than R1's split (empty →
retry; guard → mark read). One rule for "problems," not two.

---

## 2. Notice-to-owner design

### 2.1 Mechanism

```python
await smtp.send_email(
  to=[account.username],
  subject=f"[yoker-assistant] Blocked unsafe reply for: {subject}",
  body=notice_body,
)
```

- `send_email`, not `reply_email`: the notice is a new email TO the owner
  ABOUT the message, not a reply to the original sender. `reply_email` is for
  replying to the sender; `send_email` is the right primitive.
- `to=[account.username]`: the owner's address is `account.username`
  (populated from `EMAIL_USERNAME`). No new env var, no new config field.
- `body=notice_body`: plain text only. `html_body` is not set. The notice is
  an internal operational signal, not a rendered assistant reply. Plain text
  is the simplest safe form and needs no guard (the loop constructs it, not
  the agent).
- `append_to_sent=False` (default): consistent with the reply path, which
  also does not set `append_to_sent`.
- No threading headers: the notice is not part of the original email thread.
  A fresh subject with a `[yoker-assistant]` prefix makes it identifiable in
  the owner's inbox.

### 2.2 Notice content (plain text)

```
The agent produced a reply containing unsafe HTML for a message in your
inbox. The reply was blocked and was not sent to the original sender.

  Subject: {msg subject}
  From: {msg from}
  Date: {msg date}

The message has been left unread and will be retried on the next poll
(currently every {poll_interval} seconds). If the agent has been fixed by
then, the retry will succeed and the reply will be sent.

To stop further retries, either delete the message or mark it as read
manually.
```

This is a short, factual notice. It tells the owner:
- What happened (unsafe HTML, blocked).
- Which message (subject/from/date for identification).
- What happens next (automatic retry, when).
- How to stop it (delete or mark read).

No HTML, no attachments, no threading. Constructed by the loop from the
fetched `msg` dict and the `_POLL_INTERVAL` constant.

### 2.3 Where the notice code lives

A small helper in `loop.py`:

```python
async def _send_guard_notice(smtp, account, msg, poll_interval: float) -> None:
  subject = msg.get("subject", "(no subject)")
  body = (
    "The agent produced a reply containing unsafe HTML for a message in "
    "your inbox. The reply was blocked and was not sent to the original "
    f"sender.\n\n"
    f"  Subject: {subject}\n"
    f"  From: {msg.get('from', '?')}\n"
    f"  Date: {msg.get('date', '?')}\n\n"
    f"The message has been left unread and will be retried on the next "
    f"poll (currently every {poll_interval} seconds). If the agent has "
    "been fixed by then, the retry will succeed and the reply will be "
    "sent.\n\n"
    "To stop further retries, either delete the message or mark it as "
    "read manually."
  )
  await smtp.send_email(
    to=[account.username],
    subject=f"[yoker-assistant] Blocked unsafe reply for: {subject}",
    body=body,
  )
```

~15 lines. No new module. The `account` is already constructed in `run()`;
it is passed down to `_process_one` (one new parameter) so the notice helper
can read `account.username`. `poll_interval` is the existing
`_POLL_INTERVAL` constant.

### 2.4 Does the notice go through the guard?

No. The guard checks AGENT output (`reply_html`). The notice is constructed
by the loop from a plain-text template. It is safe by construction. No
guard call on the notice body.

### 2.5 Does the notice go through the recipient whitelist?

Yes — `send_email` enforces `EMAIL_RECIPIENT_ADDRESSES` on all recipients.
The owner's address must be in the whitelist. The C1 startup whitelist
check (already in the plan from `security-loop.md`) must include
`account.username`, otherwise the notice itself will be blocked by
`WhitelistError`. This is a one-line addition to the C1 check: assert
`account.username` is in the whitelist at startup. This is already
implied by "the owner can receive replies" but is now load-bearing for
the notice path; it should be made explicit.

---

## 3. Updated four-way branching in `_process_one`

`_process_one` gains an `account` parameter (for the notice's
`account.username`). The branching becomes:

```python
NO_REPLY_SENTINEL = "{{NO_REPLY}}"

async def _process_one(imap, smtp, agent, account, mid: str) -> None:
  msg = await imap.fetch_message(mid, folder=_INBOX_FOLDER)
  message = build_message(msg)
  reply_html = await agent.process(message)

  # Branch 1: intentional no-reply (sentinel present)
  if NO_REPLY_SENTINEL in reply_html:
    logger.info("agent signalled no-reply; marking read and archiving",
                message_id=mid)
    await imap.mark_message(mid, _INBOX_FOLDER, "\\Seen", "add")
    await imap.move_message(mid, _INBOX_FOLDER, _ARCHIVE_FOLDER)
    return

  # Branch 2: empty reply = "a problem" → leave UNSEEN for retry
  if not reply_html.strip():
    logger.warning(
      "agent returned empty reply (no sentinel); leaving UNSEEN for retry",
      message_id=mid)
    return

  # Branch 3: HTML guard failed → block reply, leave UNSEEN, notify owner
  if _contains_unsafe_html(reply_html):
    logger.warning(
      "HTML guard rejected reply; leaving UNSEEN and notifying owner",
      message_id=mid)
    await _send_guard_notice(smtp, account, msg, _POLL_INTERVAL)
    return

  # Branch 4: normal reply → send → mark read → archive (§4.4 ordering)
  sender = parseaddr(msg.get("from", ""))[1]
  subject = msg.get("subject", "")
  await smtp.reply_email(
    to=sender,
    subject=f"Re: {subject}",
    body="",  # plain-text alternative intentionally empty (§4.3)
    html_body=reply_html,
    in_reply_to=msg.get("message_id", ""),
  )
  await imap.mark_message(mid, _INBOX_FOLDER, "\\Seen", "add")
  await imap.move_message(mid, _INBOX_FOLDER, _ARCHIVE_FOLDER)
```

### 3.1 Branch-by-branch summary (updated)

| Agent output | Loop action | Message state after | Owner notice? |
|---|---|---|---|
| Contains `{{NO_REPLY}}` | Mark read + archive | Read, in Archive | No |
| Empty / whitespace only | Nothing (leave UNSEEN) | Unread, in INBOX | No |
| Non-empty, fails HTML guard | Leave UNSEEN + send notice | Unread, in INBOX | Yes |
| Non-empty, passes guard | Send + mark read + archive | Read, in Archive | No |
| `agent.process()` raises | Outer handler: log, leave UNSEEN | Unread, in INBOX | No |

### 3.2 What changed from R1

- Branch 3: removed `mark_message(..., "\\Seen", "add")`. Added
  `_send_guard_notice(...)`. The message now stays UNSEEN and retries.
- `_process_one` signature: added `account` parameter.
- The outer `try/except` in `run()` is unchanged. The `_process_one` call
  site passes `account` (one new argument).

### 3.3 Consistency note

Branches 2 and 3 now have identical message-state handling (leave UNSEEN,
retry next iteration). The only difference is the notice. This is the
owner's "try again" framing applied uniformly to "a problem" cases. The
guard-failure case is no longer special-cased with a mark-read.

---

## 4. Scope impact

### 4.1 Files touched (delta from R1)

| File | Change vs R1 | Net lines vs R1 |
|---|---|---|
| `src/yoker_assistant/loop.py` | Add `_send_guard_notice()` helper (~15 lines); branch 3 loses `mark_message` call, gains `_send_guard_notice` call; `_process_one` gains `account` param; call site in `run()` passes `account` | +15 net |
| `src/yoker_assistant/loop.py` | C1 startup whitelist check must assert `account.username` is whitelisted (one line, made explicit) | +1 |
| `agents/assistant.md` | No change vs R1 (sentinel step 0 already in R1) | 0 |
| `tests/test_loop.py` (P3-002) | Guard-failure tests updated: assert NO `mark_message` call + assert `send_email` called with owner address; add test for notice content | ~10 net |
| `analysis/functional.md` | §7 guard-failure case updated: "leave UNSEEN, send notice" (was "mark read, don't archive"); add notice-to-owner subsection | ~10 |

### 4.2 What does NOT change vs R1

- Module structure (`loop.py` + `__main__.py`, no `handoff.py`).
- `build_message` design.
- The HTML guard itself (`_contains_unsafe_html`, the denylist, the regex).
- The `{{NO_REPLY}}` sentinel and agent.md step 0.
- Branches 1, 2, and 4.
- The SDK errata from `api-loop.md`.
- The `--once` flag, graceful shutdown, poll interval.
- The Wrapper Check (still PASS — the notice helper is a plain function).

### 4.3 No new env vars, no new folders

- Owner email: `account.username` (from existing `EMAIL_USERNAME`).
- No "Failed" folder.
- No `YOKER_OWNER_EMAIL` env var.
- The only new identifier is the `_send_guard_notice` helper function and the
  `account` parameter threaded into `_process_one`.

---

## 5. Simplicity principle check

The owner's simplicity directive is respected:

- **Option B is simpler than R1's Option A.** R1 did MORE work on guard
  failure (mark read) to prevent a silent infinite loop. R2 does LESS
  (leave UNSEEN) because the notice makes the loop visible. Less code, fewer
  state transitions, no mark_read call.
- **The notice is one `send_email` call.** No new module, no new class, no
  new env var, no new folder. The owner's address is already available via
  `account.username`.
- **The notice body is a plain-text f-string.** No HTML, no template engine,
  no rendering. ~15 lines in a helper function.
- **No "notify once" state.** The owner said this "should indeed happen
  rarely to never." Adding state to deduplicate notices would be
  over-engineering for a rare event. Repeated notices are a useful signal
  that something is persistently broken; the owner can delete the message to
  stop them.
- **One rule for "problems," not two.** R1 had split semantics (empty →
  retry; guard → mark read). R2 unifies them (both → retry). Simpler to
  explain, test, and document.
- **No manual flag removal.** The owner's concern about "remove the 'seen'
  flag" is moot — the loop never sets it on guard failure.

---

## 6. Concerns

1. **Repeated notices on persistent failure.** If the agent consistently
   produces unsafe HTML for a message, the owner gets one notice per poll
   interval (default 60s → up to 60/hour). The owner said this "should
   indeed happen rarely to never," so this is a non-issue in practice. If it
   does happen, the notices are a useful signal and the owner can delete the
   message or mark it read. No rate-limiting is added. Flag for the owner:
   if repeated-notice noise is a concern, the poll interval can be tuned
   (`YOKER_POLL_INTERVAL`) or a "notify once per message" state can be added
   in a follow-up (out of scope for the first pass).

2. **Notice itself blocked by whitelist.** If `account.username` is not in
   `EMAIL_RECIPIENT_ADDRESSES`, `send_email` raises `WhitelistError`. The C1
   startup whitelist check must explicitly assert `account.username` is
   whitelisted. This is a one-line addition and is already implied by "the
   owner can receive replies at this address." The notice path makes it
   load-bearing; the startup check must fail fast if the owner's address is
   not whitelisted.

3. **Notice exception handling.** If `send_email` raises (SMTP failure,
   whitelist error), the outer `try/except` in `run()` catches it, logs, and
   leaves the message UNSEEN. The guard-failure retry still happens on the
   next iteration; the notice is retried too. No special handling needed.
   The unsafe reply is still blocked (it was never sent). Acceptable.

4. **Guard false-positive + notice spam.** If the guard has a false
   positive (unlikely with the current denylist), the owner gets a notice
   for a message that would have been safe. The message retries; if the
   agent produces the same output, the guard fires again. The owner can
   inspect the notice, identify the false positive, and either tune the
   guard or mark the message read. Acceptable for a demo and aligned with
   "inform the owner."

5. **No change to R1's sentinel, guard, or branches 1/2/4.** Only branch 3
   and the notice helper are new in R2.

---

## 7. Summary of changes to the implementation plan (R1 → R2)

1. **Branch 3 (guard failure): revert the mark-read.** The message is left
   UNSEEN, not marked read. It retries automatically on the next iteration.
   This answers the owner's reprocessing question: no manual flag removal
   needed.

2. **Add `_send_guard_notice()` helper in `loop.py`.** Sends a plain-text
   notice to `account.username` via `smtp.send_email`. ~15 lines. No new
   module, no new env var, no new folder.

3. **Thread `account` into `_process_one`.** One new parameter, one new
   argument at the call site. Needed for `account.username` in the notice.

4. **C1 startup whitelist check: assert `account.username` is whitelisted.**
   One line, made explicit because the notice path depends on it.

5. **`functional.md` §7: update guard-failure case** from "mark read, don't
   archive" to "leave UNSEEN, send notice." Add a notice-to-owner
   subsection documenting the mechanism, content, and owner-email source.

6. **P3-002 tests: update guard-failure tests** to assert NO `mark_message`
   call (message stays UNSEEN) + assert `send_email` called with
   `[account.username]`. Add a test for the notice subject/body content.

7. **All other R1 plan items are unchanged** (sentinel, guard function,
   branches 1/2/4, module structure, `build_message`, SDK errata, Wrapper
   Check).

This revision is ready to be posted as a PR comment on PR #7 for owner
approval. No implementation is started until the owner confirms.