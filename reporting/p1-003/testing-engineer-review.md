# Testing-Engineer Review — P1-003 (Mailbox Seam)

Reviewed artifacts:
- `src/yoker_assistant/mailbox.py`
- `tests/test_mailbox.py`
- `TODO.md` (P1-003 scope + acceptance, P3-003 plan)

Test run: `uv run pytest tests/test_mailbox.py -v` → 1 passed in 1.47s.

## Verdict

**Approved** — with two non-blocking notes (one regression-test recommendation,
one P3-003 impact flag). No blocking test gap against P1-003's stated
acceptance. The blocking `html_body=` routing acceptance is satisfied by the
implementation and verified by code review; a dedicated regression test is
recommended but not blocking.

## P1-003 Acceptance Mapping

P1-003 acceptance (TODO line 106-109):
> module imports; each method delegates to exactly one `simple_email_gw` call,
> except `reply()` which branches between `reply_email` and `send_email` on
> `in_reply_to` presence; no inline agent/reasoning logic.

| Acceptance clause | Testable in isolation? | Covered by smoke test? |
|---|---|---|
| module imports | yes | yes — `from yoker_assistant.mailbox import Mailbox` |
| 7 methods present on the surface | yes | yes — `hasattr` loop over the 7 names |
| each method delegates to exactly one gw call | yes (with stubs) | no — explicitly P3-003 territory |
| `reply()` branches on `in_reply_to` | yes (with stubs) | no — explicitly P3-003 territory |
| no inline agent/reasoning logic | no (code-review concern) | n/a |

The delegation-mapping and `reply()` branching assertions are the planned
content of P3-003 ("assert the seam methods map to the expected client calls ...
DI approach, not monkeypatching"). Deferring them is consistent with the TODO,
not a gap introduced by the slim cut.

## Smoke Test Quality

`test_mailbox_constructs_without_network`:
- **No network:** `EmailAccount` is a pydantic model (`__init__(self, /, **data)`),
  `IMAPClient`/`SMTPClient` constructors only store the account reference
  (`__init__(self, account: EmailAccount) -> None`). No sockets opened. Test
  runtime 1.47s confirms no connection attempt. Not flaky.
- **Meaningful assertion:** verifies the class is constructible end-to-end
  (pydantic validation of a dummy account + IMAP/SMTP client wiring) and the
  seven-method surface exists. This is above "just imports" — it exercises the
  constructor's integration with `simple_email_gw`'s public surface.
- **Proportionate:** for a slim demo/tutorial seam where full DI behavior tests
  are explicitly deferred to P3-003, one smoke test is proportionate. Adding
  more here would duplicate P3-003.

## Non-Blocking Note 1 — `reply()` HTML routing regression test

The blocking acceptance check (TODO line 110-113) requires `reply()` to route
HTML through `simple_email_gw`'s `html_body=` kwarg, not `body=`. The
implementation satisfies this (mailbox.py:70-83): both the `reply_email` and
`send_email` branches pass `body=text_body` (plain-text fallback, defaults to
"") and `html_body=html_body` (the agent's HTML output).

**This blocking acceptance is satisfied by code inspection.** A test is not
required for P1-003 to merge.

**Recommendation (non-blocking):** add a small regression test that asserts
`html_body=` is the kwarg carrying the HTML, and `body=` carries only the
plain-text fallback. Without it, a future refactor could silently collapse
`html_body` into `body` and ship plaintext replies (the exact failure mode the
blocking check exists to prevent) with no test signal.

Two options, either acceptable:
1. **Now, via monkeypatch** — replace `mailbox._smtp` with a stub recording
   call kwargs; assert `html_body` == the HTML arg and `body` == `text_body`.
   ~15 lines. Fits the slim steer.
2. **In P3-003, via DI** — reintroduce the `imap_client`/`smtp_client`
   constructor kwargs (see Note 2) and assert the same thing through the
   documented DI surface.

I lean toward option 1 landing alongside P1-003 because the security item is
marked blocking and P3-003's timeline is not guaranteed; but this is the
owner's call against the slimness steer. Either way, the test should exist
before P2-007 wires live replies.

**This is non-blocking for P1-003 approval.** The blocking acceptance is met by
the implementation; the gap is a hardening/regression gap, not an
acceptance-criteria gap.

## Non-Blocking Note 2 — P3-003 impact from dropped DI kwargs

P1-003 scope (TODO line 88-91) explicitly specified the constructor:
```
Mailbox(account, *, inbox_folder='INBOX', archive_folder='Archive',
        imap_client=None, smtp_client=None)
```
with: "The `imap_client`/`smtp_client` kwargs are for P3-003
dependency-injected stubs."

The slim implementation dropped `imap_client`/`smtp_client` (mailbox.py:20-31).
P3-003 (TODO line 343-344) states: "Stub clients injected via
`Mailbox(..., imap_client=..., smtp_client=...)` ... DI approach, not
monkeypatching."

**Impact:** P3-003 will need to either
- reintroduce the two DI kwargs (a small constructor change, plus rerouting
  `self._imap`/`self._smtp` to accept the injected instances), or
- abandon the documented DI approach and monkeypatch `mailbox._imap`/`_smtp`
  per test.

The second option contradicts P3-003's stated acceptance ("DI approach, not
monkeypatching"). So in practice P3-003 will have to add the DI surface back.

**This is a P1-003 scope deviation** (the constructor signature differs from
the documented scope) but not a P1-003 *acceptance* deviation (acceptance is
silent on the constructor signature). Non-blocking for P1-003. Flag for the
P3-003 author so it's not a surprise.

## Other P1-003 Scope Items Not Implemented (context, not test gaps)

These are scope reductions the owner accepted under the slim steer, not testing
gaps. Listed for completeness; no test action recommended here:
- `__aenter__`/`__aexit__` (scope line 75) — not implemented.
- `EmailMessage` typed dataclass return from `fetch()` (scope line 78-83) —
  `fetch()` returns the gateway dict verbatim. This is also a P2-006 contract
  dependency (the handoff builder expects `EmailMessage`); flag for P2-006.
- `__repr__` credential redaction (scope line 103) — not implemented.
- `ServerConfig`/`get_accounts()` construction (scope line 95-97) — not
  implemented; `Mailbox` takes a pre-built `EmailAccount`.

## Blocking Acceptance Check #2 (startup whitelist-enabled assert)

TODO line 114-116 requires a startup assert that
`get_recipient_whitelist().enabled is True` and non-empty. This is a loop/init
concern (P2-005), not the mailbox seam's responsibility, and the mailbox module
correctly does not implement it. Not a P1-003 testing gap.

## Coverage Summary

- P1-003 acceptance clauses testable in isolation: 2 of 4 (imports, method
  surface). Both covered. The other 2 (delegation mapping, reply branching)
  are explicitly P3-003 scope.
- Blocking acceptance: `html_body=` routing — satisfied by implementation,
  verified by code review; regression test recommended (non-blocking).
- Smoke test quality: no network, not flaky, meaningful assertion,
  proportionate to the slim steer.
- Downstream impact: dropped DI kwargs create P3-003 rework; flag, do not
  block.

## Recommended Actions (none blocking)

1. (P1-003, optional) Add the `reply()` `html_body=` routing regression test
   via monkeypatch (~15 lines), or explicitly defer it to P3-003 and record
   that decision on the P3-003 entry.
2. (P3-003) Plan to reintroduce `imap_client`/`smtp_client` DI kwargs on the
   `Mailbox` constructor before writing the DI-based seam tests.
3. (P2-006) Note that `fetch()` currently returns a dict, not the `EmailMessage`
   dataclass the handoff builder contract assumes.