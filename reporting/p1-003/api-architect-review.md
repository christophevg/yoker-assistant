# API Architect Review — P1-003 Mailbox Seam (SLIM)

- **Task:** P1-003 Implement the mailbox seam module
- **Branch:** `feature/p1-003-mailbox-seam`
- **Implementation:** `src/yoker_assistant/mailbox.py` (91 lines)
- **Test:** `tests/test_mailbox.py` (smoke test, 26 lines)
- **Reviewer:** api-architect
- **Date:** 2026-07-20
- **Steer context:** Owner directive — keep it slim; a demo/tutorial
  project; avoid over-engineering. The cross-domain consensus contract
  is treated as a **ceiling, not a target**. Trimming abstractions the
  owner flagged is sanctioned; the review calibrates against "slim, not
  elaborate", not against the full consensus design.
- **Reference design:** `analysis/api-p1-003-mailbox.md`
- **Cross-reviews:** `reporting/p1-003/consensus.md`,
  `reporting/p1-003/functional-analyst-review.md`

## Verdict

**approved** — The slim seam satisfies the loop's needs (§2.1 steps
1-6), honors the §7 error contract (propagate, don't swallow), gets the
1:1 delegation and `html_body=` routing correct in both branches, and
keeps the typing sound under mypy strict. The trimmed abstractions are
appropriate given the owner's explicit slimness steer; none of the cuts
break anything the loop needs. One minor design deviation
(`in_reply_to` folded into `reply()` instead of a separate `send()`
method) is actually a net simplification and is correct. Non-blocking
observations are noted for P2-006 and P3-003.

## Loop Coverage — §2.1 steps 1-6

| §2.1 step | Seam method | Gateway call | Covered |
|---|---|---|---|
| 1. Poll (search INBOX UNSEEN) | `unread_ids()` | `imap.search(folder, criteria="UNSEEN")` | yes |
| 2. Sleep if empty | (loop) | — | n/a |
| 3. Fetch | `fetch(id)` | `imap.fetch_message(id, folder)` | yes |
| 4. Handoff | (loop builds message from dict) | — | n/a |
| 5. Reply | `reply(to, subject, html_body, in_reply_to)` | `smtp.reply_email` / `smtp.send_email` | yes |
| 6. Settle (mark read, archive) | `mark_read(id)`; `archive(id)` | `imap.mark_message`; `imap.move_message` | yes |

All six loop-relevant steps have a corresponding seam method with the
correct 1:1 gateway call. The seam does not own step 2 (sleep) or step
4 (handoff construction) — those are the loop's and the handoff
builder's jobs respectively, matching the §2.2 "two halves do not
bleed" boundary.

## §7 Error Contract — propagate, don't swallow

`mailbox.py` contains zero `try`/`except` blocks. Every gateway
exception (`RuntimeError` from IMAP drops, `WhitelistError` from
`reply_email`'s recipient check, `SecurityError`, `ValueError` from
invalid search criteria, etc.) propagates unchanged to the caller.
This is exactly what §7 prescribes:

- IMAP/SMTP connection failure → propagates → loop logs and backs off.
- Reply send failure (`WhitelistError`, SMTP error) → propagates →
  loop does not mark read; retries next iteration.
- Unexpected exception → propagates → loop skips the message and
  continues.

The dropped `MailboxError` wrapping was explicitly a
**recommendation, not a blocking requirement** in the design doc
("the first pass may let gateway exceptions propagate raw if the
loop's logging already sanitizes them"). The slim version takes that
option. The blocking concern was `html_body=` routing and the env-var
rename — both are present (verified below and in the
functional-analyst review).

## 1:1 Delegation Correctness

Verified against the installed `simple_email_gw` 0.3.0 signatures
(`.venv/lib/python3.12/site-packages/simple_email_gw/{imap,smtp}/client.py`):

| Seam call | Gateway signature | Match |
|---|---|---|
| `await self._imap.connect()` | `async def connect(self) -> IMAP4_SSL` | yes |
| `await self._imap.disconnect()` | `async def disconnect(self) -> None` | yes |
| `await self._imap.search(folder=self._inbox_folder, criteria="UNSEEN")` | `async def search(self, folder="INBOX", criteria="ALL", limit=50) -> list[str]` | yes |
| `await self._imap.fetch_message(message_id, folder=self._inbox_folder)` | `async def fetch_message(self, message_id: str, folder: str = "INBOX") -> dict[str, Any]` | yes |
| `await self._smtp.reply_email(to=, subject=, body=text_body, html_body=html_body, in_reply_to=)` | `async def reply_email(self, to: str, subject: str, body: str, in_reply_to: str, references=None, html_body=None, ...)` | yes |
| `await self._smtp.send_email(to=[to], subject=, body=text_body, html_body=html_body)` | `async def send_email(self, to: list[str], subject: str, body: str, ..., html_body=None, ...)` | yes |
| `await self._imap.mark_message(message_id, self._inbox_folder, "\\Seen", "add")` | `async def mark_message(self, message_id: str, folder: str, flag: str, action: str = "add") -> bool` | yes |
| `await self._imap.move_message(message_id, self._inbox_folder, self._archive_folder)` | `async def move_message(self, message_id: str, source_folder: str, dest_folder: str) -> bool` | yes |

Every call site matches the gateway's parameter names and types. No
wrong arg names, no wrong defaults, no missing `await`. The
`to=[to]` wrapping in the `send_email` branch correctly converts the
single-recipient `str` the seam accepts into the `list[str]` the
gateway requires.

### `reply()` branch logic

```python
if in_reply_to is not None:
    reply_email(to=, subject=, body=text_body, html_body=html_body, in_reply_to=)
else:
    send_email(to=[to], subject=, body=text_body, html_body=html_body)
```

The branch is on `in_reply_to is not None` — exactly the
`in_reply_to`-presence predicate the design specified. This is
transport routing (which gateway method sends the message), not
business logic. The branch lives in the seam so the loop (P2-005)
does not have to know about `reply_email` vs `send_email`.

**Minor design deviation (non-blocking):** the consensus design
specified `reply(to, subject, html_body, in_reply_to, *, text_body="")`
with `in_reply_to` a required positional, and a *separate* `send()`
method for the P2-007 fallback. The slim version makes
`in_reply_to: str | None = None` and folds both paths into one
method. This is a cleaner, slimmer surface — one method instead of
two — and the routing is correct in both branches. The P2-007
fallback is no longer a new method to add; it is just calling
`reply(..., in_reply_to=None)`. This is a net win under the slim
steer. P2-007's task scope should be updated to reflect that the
`send()` method is no longer needed; the `Re:` subject prefix
remains the loop's job.

## `html_body=` Routing — BLOCKING SECURITY ITEM

Verified in both branches (lines 70-76 and 78-83):

- `reply_email` branch: `html_body=html_body` (line 74) — correct.
- `send_email` branch: `html_body=html_body` (line 82) — correct.
- `body=text_body` (the plain-text fallback, empty by default) in
  both branches — correct.

The agent's HTML is never passed as `body=`. The gateway sets
`Content-Type: text/html` via `msg.add_alternative(html_body,
subtype="html")` when `html_body` is provided (verified in
`simple_email_gw/smtp/client.py`). The blocking security concern is
closed.

## Dropped Abstractions — Did the trim go too far?

Cross-checked against the consensus contract and the loop's actual
needs:

| Abstraction | Dropped? | Impact on loop (P2-005) | Impact on P2-006 / P3-003 | Verdict |
|---|---|---|---|---|
| `EmailMessage` dataclass | Yes | None — loop reads dict keys directly | P2-006 handoff builder references it; will need to accept `dict[str, Any]` or define its own TypedDict/dataclass at that point. The `fetch()` docstring preserves the key contract (`id`, `folder`, `subject`, `from`, `to`, `date`, `body`, `attachments`, `read`, `message_id`, `references`) — nothing is lost, just untyped. | appropriate; P2-006 owns the typed shape when it needs it |
| DI kwargs (`imap_client`/`smtp_client`) | Yes | None | P3-003 will monkeypatch `_imap`/`_smtp` instead of injecting. Slightly less clean but trivially workable for a 7-method facade. | appropriate; P3-003 adapts |
| `__aenter__`/`__aexit__` | Yes | None — loop calls `await connect()` / `await close()` explicitly. The design doc explicitly sanctioned this: "The loop may also construct it once and call connect()/close() explicitly to span many iterations." | None | appropriate; sanctioned in design |
| `MailboxError` wrapping | Yes | None — exceptions propagate raw; loop's logging handles sanitization | None | appropriate; was non-blocking in design |
| `assert_reply_safety_enabled` | Yes (deferred to P2-005) | Correct seam/loop boundary — a fail-closed startup assertion belongs in the loop, where it can refuse to enter the run state, not in a library seam constructed in tests | None | appropriate; docstring makes the boundary explicit |
| `__repr__` | Yes | None | None — pydantic `SecretStr` redaction on `EmailAccount` is the remaining safeguard | appropriate; non-blocking |
| Logging | Yes | None — gateway's `safety.audit` logs stand; loop logs at INFO | None | appropriate; non-blocking |

### Did the trim go too far?

No. The seam's job is to be a thin facade: one object instead of two,
folder defaults in one place, the `reply()` branch, and the
security-load-bearing `html_body=` parameter name. All four are
present. None of the dropped abstractions break a §2.1 step or a §7
error-handling rule. The downstream consequences (P2-006 defines its
own typed shape; P3-003 monkeypatches instead of injecting) are
real but minor, and each is correctly owned by the downstream task
rather than P1-003. The owner's "slim, not elaborate" directive is
honored without crossing into "too slim to function".

The one place the trim could be argued to cost future work is the
`EmailMessage` dataclass: P2-006's handoff builder now has to define
its own typed shape rather than importing one from P1-003. But the
design doc itself flagged this as a deferral option ("a TypedDict
can be added later if the handoff builder P2-006 would benefit"),
and the key contract is preserved in the `fetch()` docstring. Under
the slim steer, making P2-006 own the shape it actually consumes is
correct — it avoids a speculative shared type that may not match
what P2-006 ends up needing.

## Correctness Bugs

None found. Specifically checked:

- All awaits present on every async gateway call.
- `list(await self._imap.search(...))` — the gateway returns
  `list[str]`; `list(...)` copies it, which is harmless and isolates
  the caller from the gateway's internal list.
- `bool(await self._imap.mark_message(...))` and
  `bool(await self._imap.move_message(...))` — both gateway methods
  already return `bool`; the `bool()` wrap is defensive but
  harmless and satisfies mypy strict without a cast.
- `to=[to]` in the `send_email` branch correctly wraps the single
  address for the gateway's `list[str]` parameter.
- `text_body=""` default is passed as `body=text_body` in both
  branches — the gateway requires `body` (plain text) even when
  `html_body` is set; the empty-string default satisfies that
  without imposing a non-empty plain-text alternative on the caller.
- No off-by-one or wrong-default issues in folder defaults
  (`inbox_folder="INBOX"`, `archive_folder="Archive"`).

## mypy Strict

`uv run mypy src` passes (per functional-analyst review, reproduced
in the consensus). The typing is sound:

- `dict[str, Any]` on `fetch()` is honest — the gateway returns
  exactly that shape; pretending more would be false precision.
- `list[str]` on `unread_ids()` matches the gateway's `list[str]`.
- `str | None` on `in_reply_to` correctly models the optional
  threading header.
- Keyword-only `text_body: str = ""` is correctly marked with `*`.
- No `Any` leak beyond the gateway's own dict shape.
- No untyped methods; no missing return annotations.

The `from __future__ import annotations` the design suggested is
omitted (the slim version uses direct annotations). Under Python 3.12
this is not required for the syntax used (`str | None`, `list[str]`,
`dict[str, Any]` all work natively). mypy strict passing confirms
this. Non-issue.

## Non-blocking Observations (notes for downstream tasks)

These are not P1-003 defects. They are consequences of the slim
drops that downstream tasks will need to handle. Recording them here
so they are not lost:

1. **P2-006 (handoff builder)** references "the `EmailMessage`
   dataclass defined in P1-003". The slim version drops that
   dataclass; `fetch()` returns `dict[str, Any]` with the keys
   listed in its docstring. P2-006 should either accept the dict
   directly (typed as a TypedDict or `dict[str, Any]`) or define
   its own dataclass at that point. The key contract is preserved
   in the docstring; only the typed shape is deferred.

2. **P2-007 (`Re:` fallback)** no longer needs a new `send()` seam
   method — the slim `reply()` already covers the
   `in_reply_to=None` path via `send_email`. P2-007's remaining
   scope is the `Re: <subject>` prefix construction in the loop and
   the decision logic for when no Message-ID is available. Update
   P2-007's task scope to reflect this.

3. **P3-003 (mailbox seam tests)** specifies DI via constructor
   kwargs. The DI kwargs are dropped per the slim steer. P3-003
   will need to monkeypatch `_imap`/`_smtp` directly, or
   reintroduce a minimal DI surface at that point if the owner
   prefers DI over monkeypatching. This is a P3-003 decision, not
   a P1-003 defect — the prompt explicitly authorized dropping the
   DI kwargs.

4. **P2-005 (the loop)** owns the startup whitelist-enabled
   assertion and the §7 backoff/skip policy. The seam's docstring
   makes this boundary explicit (lines 6-7). The blocking
   env-var rename (`EMAIL_RECIPIENT_WHITELIST_ADDRESSES`) has
   already landed in `.env.example` and `README.md` (verified in
   the functional-analyst review).

5. **`__repr__` redaction** is not defined. Pydantic's `SecretStr`
   redaction on `EmailAccount` is the remaining safeguard. If a
   future logging posture review wants belt-and-suspenders
   redaction on the `Mailbox` object itself, a `__repr__` can be
   added in a hardening pass. Non-blocking.

## REST / API-Design Compliance

This is a Python library seam, not an HTTP API, so the RESTful
design principles do not apply directly. The relevant
api-architect concerns are naming and surface discipline:

- Method names are verbs describing seam operations (`connect`,
  `close`, `unread_ids`, `fetch`, `reply`, `mark_read`,
  `archive`) — appropriate for a procedural facade.
- No RPC-over-HTTP concerns.
- The public surface is minimal: 7 async methods + `__init__`.
  No dead surface, no speculative generality.
- The `reply()` signature (`to, subject, html_body, in_reply_to,
  *, text_body=""`) makes the security-load-bearing parameter
  (`html_body`) positional and explicit, and the plain-text
  fallback keyword-only. This is the naming discipline the
  security-engineer asked for, preserved under the slim trim.

## Summary

The slim seam is correct, sound, and appropriately minimal. Both
blocking security items are satisfied. The 1:1 delegation matches
the installed gateway signatures exactly. The `html_body=` routing
is correct in both branches. mypy strict passes. The dropped
abstractions are sanctioned by the owner's slimness steer and do
not break any §2.1 step or §7 error-handling rule. The downstream
consequences (P2-006 typed shape, P3-003 test injection, P2-007
`send()` method no longer needed) are correctly owned by those
tasks. No correctness bugs found.