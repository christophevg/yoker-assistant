# Code Review — P1-003: Mailbox Seam

**Task:** P1-003 — Implement the mailbox seam module
**Reviewer:** code-reviewer
**Verdict:** **Approved** (with non-blocking notes)
**Files reviewed:**
- `src/yoker_assistant/mailbox.py` (91 lines)
- `tests/test_mailbox.py`

## Summary

The slim P1-003 mailbox seam is a single `Mailbox` class wrapping one
`IMAPClient` + one `SMTPClient` over one `EmailAccount`, exposing seven
async methods. Each method delegates to exactly one gateway call; `reply()`
is the sole branch, routing on `in_reply_to` presence (transport routing,
not business logic). The implementation is tight, altitude-correct, and
matches the owner's slimness steer.

## Tight Code Assessment

- One `Mailbox` class, one responsibility (transport seam), one
  composition (IMAPClient + SMTPClient over EmailAccount). No premature
  abstractions, no protocol layers, nofacade-of-a-facade.
- Seven async methods, each a thin delegation: `connect`, `unread_ids`,
  `fetch`, `reply`, `mark_read`, `archive`, `close`. Method count earned
  (one per distinct gateway operation the loop needs).
- `reply()` branches on `in_reply_to is not None` → `reply_email` vs
  `send_email`. This is transport routing, not business logic; it stays
  in the seam.
- The module docstring is excellent WHY documentation: it states
  explicitly what is deliberately NOT in the seam (no allowlist, no
  exception wrapping, no HTML re-rendering). That negative-space
  documentation is exactly right for a seam module.
- `bool()`/`list()` coercion on gateway return values is earned — keeps
  the seam's typed surface honest without inventing a new model.
- `inbox_folder`/`archive_folder` parameters earned (loop config flows
  through the seam rather than being re-passed per call).
- `text_body` parameter on `reply()` earned (the §4.3 accessibility
  hook — intentionally empty in the first pass, but the slot exists so
  P2-007 does not need to reopen the seam).

## Design Assessment

The seam is the right altitude: it hides `simple_email_gw`'s
`IMAPClient`/`SMTPClient` pair behind one long-lived object the loop can
hold, and it normalizes the connect/disconnect lifecycle into
`connect()`/`close()`. It does not invent a repository, a port, or an
adapter-of-an-adapter. The `reply()` routing branch is correctly placed
in the seam (it is transport routing) and would be wrong to push up into
the loop.

The slimness decision (dropping `__aenter__`/`__aexit__` and the
`imap_client`/`smtp_client` DI kwargs) is consistent: the loop owns the
lifecycle via explicit `await connect()`/`await close()` calls, and tests
can monkeypatch `self._imap`/`self._smtp` if needed. P3-003 will decide
whether to reintroduce a minimal DI surface or use monkeypatching.

## Quality Issues

### M1 (medium) — spec deviation: `__aenter__`/`__aexit__` vs explicit connect/close

`analysis/functional.md` §2.4 (errata paragraph and snippet comment) and
the P1-003 task scope in `TODO.md` stated `Mailbox` implements
`__aenter__`/`__aexit__`. The slim implementation dropped the
context-manager protocol in favor of explicit `async connect()`/`async
close()` methods, per the owner's slimness directive.

**Resolution:** reconcile `functional.md` §2.4 to record the
explicit-connect decision (being applied in this session). This is a
documentation reconciliation, not a code change — the slim implementation
is the source of truth. Non-blocking for the code verdict.

### L1 — `self._account` is dead state (being applied)

`Mailbox.__init__` stores `self._account = account` but no method reads
it after construction. The `IMAPClient`/`SMTPClient` are constructed
upfront from `account` and hold everything they need; `self._account` is
unused dead state. **Resolution:** drop `self._account` (being applied as
a follow-up edit). Non-blocking.

### L2 — `fetch()` result local is redundant (being applied)

`fetch()` binds a `result = await self._imap.fetch_message(...)` local
and returns it on the next line. Collapse to a one-liner `return await
self._imap.fetch_message(...)`. **Resolution:** being applied. Non-blocking.

## Test Coverage

The `tests/test_mailbox.py` smoke test is the right scope for P1-003:
it exercises import, construction, and the `html_body=` routing branch
(the one piece of logic the seam owns). It does NOT attempt behavior
tests against the gateway — that is correctly P3-003's job (the
testing-engineer concurs). P3-003 will expand the `html_body=` routing
test to cover both `in_reply_to` branches and land the
DI-vs-monkeypatching decision.

## Documentation

The module docstring is the standout: it documents the WHY (what the
seam is for) AND the negative space (what is deliberately NOT here — no
allowlist, no exception wrapping, no HTML re-rendering). This is the
correct docstring posture for a seam module. No additional documentation
is required at this altitude.

## Maintainability Score

**4.8 / 5**

Tight, single-responsibility, correctly-altituded seam. The only
deductions are the dead `self._account` state (L1) and the redundant
`fetch()` local (L2) — both non-blocking and being applied. The M1 spec
deviation is a documentation issue, not a code-quality issue.

## Cross-Domain Concerns

- **M1 (spec deviation):** resolved before P2-005 wires the loop.
  `functional.md` is being reconciled in this session to record the
  explicit-connect decision.
- **`html_body=` routing:** verified correct — `Mailbox.reply()` forwards
  `html_body=` to the gateway (both `reply_email` and `send_email`
  branches), never `body=`. The §4.3 clarification holds. A small
  regression test lands in P1-003; P3-003 expands it.
- **Recipient allowlist:** correctly NOT in the seam — `reply()`
  delegates to `simple_email_gw`, which enforces
  `EMAIL_RECIPIENT_WHITELIST_ADDRESSES`. The module docstring states this
  explicitly.
- **Credential handling:** no `get_secret_value()` calls outside gateway
  invocation; `Mailbox.__repr__` not overridden in the slim version but
  also does not surface the `EmailAccount` (it lives only in
  `__init__`'s local scope after constructing the clients). No leak.

## Recommendations

1. Apply L1 (drop `self._account`) and L2 (collapse `fetch()` to a
   one-liner). Both non-blocking.
2. Reconcile `functional.md` §2.4 to match the slim implementation
   (M1 — being applied in this session).
3. Leave L3 (the `connect()` docstring is pure WHAT) as-is for symmetry
   with the other one-line method docstrings; optional polish, not
   required.
4. P3-003 owns the expanded `html_body=` routing regression test and the
   DI-vs-monkeypatching decision — recorded in TODO.md.

## Conclusion

Approved. The slim P1-003 mailbox seam is tight, correctly-altituded,
and matches the owner's slimness steer. The M1 spec deviation is a
documentation reconciliation (being applied), not a code defect. L1 and
L2 are non-blocking cleanups (being applied). The seam is ready for
P2-005 to wire the loop and P2-007 to wire live replies.