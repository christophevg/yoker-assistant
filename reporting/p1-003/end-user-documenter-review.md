# P1-003 end-user-documenter review (MINIMAL scope)

Owner directive: keep it slim. P1-003 is an internal seam module
(`src/yoker_assistant/mailbox.py`); the only user-facing artifacts in this PR
are the `.env.example`/`README.md` env-var rename errata. The full README
tutorial is P4-001 (deferred).

## Scope reviewed

- `src/yoker_assistant/mailbox.py` — module docstring + method docstrings
- `.env.example` — the `EMAIL_RECIPIENT_WHITELIST_ADDRESSES` rename
- `README.md` — the Configuration section
- `TODO.md` — P4-001 entry (confirm tutorial is deferred)

## Findings

### Module docstring (`mailbox.py` lines 1-10)

Clear and accurate. It states:

- What the seam is: a thin async seam over `simple_email_gw`'s IMAP/SMTP
  clients.
- What it delegates to: exactly one `simple_email_gw` call per method, with
  `reply()` branching on `in_reply_to` (transport routing, not business
  logic).
- What it deliberately does NOT do: no business logic, no recipient
  allowlist (lives in the gateway), no HTML re-rendering, no exception
  wrapping.
- The deferred startup whitelist assertion is explicitly noted: "the loop
  (P2-005) owns backoff/skip and the startup whitelist-enabled check."
- The blocking security requirement is noted: HTML replies route through
  the gateway's `html_body=` kwarg so they are sent as `text/html`.

This satisfies the review questions for the module docstring: it is clear
what the seam does, what it delegates to, and it notes the deferred P2-005
startup whitelist assertion.

### Method docstrings (`mailbox.py` lines 34, 38, 42, 46-51, 64-68, 86, 90)

One-line (or short-block) docstrings, each explaining the delegation:
`connect()` → `await self._imap.connect()`; `close()` → `await
self._imap.disconnect()`; `unread_ids()` → `search(folder=...,
criteria="UNSEEN")`; `fetch()` → `fetch_message(...)` with the returned
keys enumerated; `reply()` → `reply_email` (threaded) or `send_email` with
the `html_body=`/`body=` routing explained; `mark_read()` →
`mark_message(..., flag="\\Seen", action="add")`; `archive()` →
`move_message(...)`.

Useful for a maintainer reading the seam: each docstring makes the
delegation target and the argument shape explicit without restating the
body. The `fetch()` docstring enumerating the returned dict keys is a
nice touch — it documents the shared contract inline. No issues.

### `.env.example` / `README.md` env-var rename

- `.env.example` line 15: `EMAIL_RECIPIENT_WHITELIST_ADDRESSES=owner@example.com`
- `README.md` line 72: `EMAIL_RECIPIENT_WHITELIST_ADDRESSES=owner@example.com`
- `README.md` lines 75-79: prose explains the env var is the primary
  reply-safety boundary, set to the single owner address, and that it is a
  `simple-email-gw` config concern (not package code).

`grep` for the stale `EMAIL_RECIPIENT_ADDRESSES` in both files returns zero
matches. The rename is correct and consistent across both user-facing
artifacts.

### User-facing doc needed for P1-003 specifically

None beyond what is already present. The README Configuration section
already documents the corrected env-var name and the reply-safety
semantics. The full tutorial (build story, persistent-session
architecture, custom-tool story, dual-mode, git demo beat) is explicitly
owned by P4-001 and is correctly deferred — no partial tutorial should
land here. The `.env.example` comment block already explains the
whitelist boundary at the point of use.

## Non-blocking notes (not requiring changes)

- `TODO.md` lines 312 and 420 still reference the stale
  `EMAIL_RECIPIENT_ADDRESSES` (in the P2-007 and P4-001 entries). These
  are out of scope for the end-user-documenter (TODO.md is owned by the
  functional-analyst) and are not user-facing; flagged here only so the
  functional-analyst can correct them when those tasks are worked. They do
  not block P1-003.

## Verdict

`approved` — the module docstring clearly explains the seam and its
delegation, notes the deferred P2-005 startup whitelist assertion, and
flags the blocking HTML-routing security requirement; the method
docstrings are tight and useful; the `.env.example`/`README.md` env-var
rename is correct and consistent with no stale references; and no
additional user-facing doc is needed for P1-003 (the full tutorial is
correctly deferred to P4-001, per the owner's slim directive).