# P1-003 Cross-Domain Review Consensus

- **Task:** P1-003 Implement the mailbox seam module
- **Scope:** backend (async seam over `simple_email_gw` IMAP/SMTP)
- **Invoked agents:** api-architect, security-engineer
- **Date:** 2026-07-20

## Descope update (owner feedback)

During PR review the owner challenged the Mailbox seam:

- "Why wrap two existing classes in another class with no added benefit?"
- "How can the reply ever not be a reply?"

**Decision: descope P1-003 to errata only.** The consensus design below
(a `Mailbox` wrapper class + a `reply()` branch between `reply_email` and
`send_email`) was descoped. Specifically:

- **The `Mailbox` class is DROPPED.** No `mailbox.py`, no seam methods
  (`connect`/`unread_ids`/`fetch`/`reply`/`mark_read`/`archive`/`close`),
  no `__aenter__`/`__aexit__`, no typed `EmailMessage` dataclass.
- **The `send_reply` helper and the `in_reply_to` branch are DROPPED.**
  Every send is a reply — always `smtp.reply_email(to=...,
  subject=f"Re: {subject}", html_body=reply_html,
  in_reply_to=msg["message_id"])`. There is no `send_email` fallback
  ("how can the reply ever not be a reply?" — it cannot).
- **The loop (P2-005) uses `simple_email_gw` directly.** It constructs
  `IMAPClient(account)` + `SMTPClient(account)`, calls
  `await imap.connect()` once, polls `UNSEEN`, fetches, hands off to the
  agent, sends the reply via `smtp.reply_email(...)` (only if the agent
  produced a non-empty reply body), marks read, archives, and calls
  `await imap.disconnect()` on shutdown.
- **The only conditional is a loop concern:** "agent produced no reply
  body → skip the send." That decision lives in P2-005, not in a seam.
- **The `html_body=` routing is a loop concern** (kwarg name on the
  `smtp.reply_email(...)` call); the loop does not construct MIME.
- **P1-003 is now errata-only:** the env-var rename
  (`EMAIL_RECIPIENT_ADDRESSES` → `EMAIL_RECIPIENT_WHITELIST_ADDRESSES`)
  in `.env.example` and `README.md`, plus the `functional.md` §2.2/§2.4/
  §4.3/§4.4 corrections that record the descope.
- **P2-007 (wire reply sending) is FOLDED INTO P2-005.** The reply
  sending is a single `smtp.reply_email(...)` call in the loop; P2-007
  has no remaining scope.
- **P3-003 (mailbox seam tests) is DROPPED.** No seam to test. The
  `html_body=` routing regression test that lived in the descoped
  `test_mailbox.py` is absorbed into P3-002 (loop tests), which now
  asserts the loop calls `smtp.reply_email(..., html_body=<agent output>,
  in_reply_to=msg["message_id"])` (not `body=`, not `send_email`) and
  skips sending when the agent produces no reply body.

The original consensus design is retained below for the historical
record.

## Key decisions agreed

- **Mailbox is a thin async seam, long-lived**, implements
  `__aenter__`/`__aexit__`; holds one `IMAPClient` + one `SMTPClient`.
  (api-architect)
- **`fetch()` returns a typed `EmailMessage` dataclass** (frozen, slots) —
  shared contract for P2-006 (handoff builder) and P3-003 (tests).
  (api-architect)
- **`reply(to, subject, html_body, in_reply_to, *, text_body='')`** —
  parameter named `html_body` per security-engineer; routes to
  `simple_email_gw`'s `html_body=` (not `body=`). Branches on `in_reply_to`
  presence → `reply_email` or `send_email` fallback (transport routing, not
  business logic). (synthesis — the html_body naming resolved the only
  cross-review difference)
- **Loop owns ordering** (send → mark read → archive) and §7 error policy;
  the seam propagates exceptions without retry. (api-architect, confirmed)
- **Dependency injection** of `imap_client`/`smtp_client` via constructor
  kwargs for P3-003 testability. (api-architect)
- **Reply-safety boundary stays in `simple_email_gw`**
  (`EMAIL_RECIPIENT_WHITELIST_ADDRESSES`); the seam does NOT reinvent the
  allowlist. (security-engineer)
- **TLS inherited from `simple_email_gw`** (`ServerConfig`/`get_accounts()`);
  no hand-built downgraded `EmailAccount`. (security-engineer)
- **Credentials:** `EmailAccount.password` is a pydantic `SecretStr`;
  `Mailbox.__repr__` redacts; no `get_secret_value()` outside gateway calls.
  (security-engineer)
- **Logging:** INFO counts/events only; never bodies/credentials/full
  headers. (security-engineer)
- **functional.md §2.4 errata applied** (no async context manager on
  `simple_email_gw` clients; `Mailbox` provides its own); **§4.3
  clarification added** (HTML content-type set in `simple_email_gw` when
  `html_body` is passed; seam does not construct MIME).

## Blocking items to verify at implementation

1. `reply()` routes HTML through `html_body=` (not `body=`).
2. Startup assertion: `get_recipient_whitelist().enabled is True` and
   non-empty (fail closed for unattended operation — no silent
   reply-to-arbitrary-senders).
3. P1-002 errata: rename `EMAIL_RECIPIENT_ADDRESSES` →
   `EMAIL_RECIPIENT_WHITELIST_ADDRESSES` in `.env.example` and `README.md`
   (lands alongside P1-003; the wrong name silently disables the
   whitelist).

## New backlog item

- **S-03** recorded: file an upstream issue against `simple-email-gw` — its
  README documents the wrong env var names
  (`EMAIL_RECIPIENT_ADDRESSES` vs the actual
  `EMAIL_RECIPIENT_WHITELIST_ADDRESSES` binding). Same bug affects all
  consumers.

## Artifacts updated

- `TODO.md` — P1-003 entry expanded (scope/contract bullets, relaxed 1:1
  acceptance, blocking checks, P1-002 errata); P2-006 entry references the
  P1-003 `EmailMessage` dataclass; P3-003 entry specifies DI via
  constructor kwargs (no monkeypatching); P4-001 entry uses the correct
  env var name and calls out the silent-disable risk; new S-03 entry
  added.
- `analysis/functional.md` — §2.4 errata applied (explicit
  connect/disconnect form; note that `Mailbox` wraps the clients as an
  async context manager); §4.3 clarification added (`html_body=` routing,
  no MIME construction in the seam, plain-text alternative deferred).

## Consensus verdict

All invoked agents approve proceeding to implementation. No blocking
disagreements; the `html_body` naming synthesis resolved the only
cross-review difference. The blocking items above MUST be verified during
implementation review.