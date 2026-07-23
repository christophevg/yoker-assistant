# Phase 3 Testing Design Review — Bucket A (Q1: P3-001 / P3-002)

Reviewer: testing-engineer
Mode: Phase 3 design review (pre-implementation)
Scope: Q1 only — P3-001 handoff-contract tests and P3-002 polling-loop test additions.

## Verdict: APPROVE with changes

The plan is sound on the substance (the no-`Instructions:` regression
assertion is the real gap; the send-failure-no-archive test fills a real
P3-002 hole). The form needs adjustment: option (b) is the right call for
P3-001, and one of the three tests in the proposed `test_handoff.py` is
buggy. Details below.

## Q1 answer: (b) — no new test file

Apply the Simplicity Principle: a new test file is an indirection when it
doesn't add value beyond organization. The proposed `tests/test_handoff.py`
fails that test on two counts:

### 1. Two of three tests are duplicate assertions

| Proposed `test_handoff.py` test | Already covered by |
|---|---|
| `test_handoff_has_from_subject_date_headers_and_body` | `test_build_message_formats_headers_and_body` (line 30) |
| `test_handoff_preserves_body_verbatim_with_newlines` | `test_build_message_preserves_body_verbatim` (line 66) |
| `test_handoff_has_no_instructions_block` | **NEW — not covered** |

Re-testing the format and body-verbatim contract in a second file is the
"Duplicate assertions" anti-pattern. The existing tests already lock the
contract that would regress if the format changed — P3-001's stated
acceptance.

### 2. The "easy to move if `build_message` ever moves" argument is YAGNI

`handoff.py` was never created. `build_message` lives in `loop.py`. The
backlog predates that consolidation. Speculating a future module split to
justify a file today is speculative abstraction. If/when `build_message`
moves, the tests can move at the same commit — that's the natural time to
extract a `test_handoff.py`. Today, the cost is duplication; the benefit is
hypothetical.

### 3. The "labels the handoff contract explicitly" value survives without a file

A single new test in `tests/test_loop.py` with a clear docstring achieves
the same labeling:

```python
def test_build_message_omits_instructions_block() -> None:
  """P3-001 handoff contract: the per-email payload must NOT contain an
  ``Instructions:`` block. Identity and workflow instructions live in the
  agent definition + the one-time session-setup turn (P1-004), not in each
  email's handoff. This is the regression test that fires if someone
  reintroduces the old c3-style instructions header.
  """
  msg = {"from": "o@example.com", "subject": "Hi", "date": "D", "body": "b"}
  out = build_message(msg)
  for line in out.splitlines():
    assert not line.lower().startswith("instructions:")
```

This is one focused test, added where the other `build_message` tests
already live, with the contract concern named in the docstring. The
checkbox flips, the regression is locked, no file is created.

### 4. Bug in the proposed `test_handoff_has_no_instructions_block`

The middle assertion in the proposed test is a tautology that always
passes regardless of input:

```python
assert "instructions:" not in out.lower().split("instructions:")[0].endswith("instructions:")
```

`"foo instructions: bar".lower().split("instructions:")[0]` returns
`"foo "` — the text *before* the first delimiter. That substring never
ends with `"instructions:"` (we just split on it), so `.endswith(...)`
returns `False`, and `not False` is `True`. The assertion holds for any
input string, including ones that contain `Instructions:`. It is bloat
that looks like a real check.

The meaningful assertion in that test is the per-line `startswith` loop.
The case-sensitive `"Instructions:" not in out` is redundant with the
loop (the loop catches case-insensitively). Drop both the tautology and
the redundant check; keep the per-line loop.

### Recommendation for P3-001

- Do NOT create `tests/test_handoff.py`.
- Add `test_build_message_omits_instructions_block` (above) to
  `tests/test_loop.py` next to the existing `test_build_message_*` suite.
- Flip the P3-001 checkbox.

## P3-002 additions: approved with one adjustment

### Addition 1: send-failure-no-archive test — APPROVED as-is

```python
async def test_process_one_send_failure_does_not_archive(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  """If smtp.reply_email raises, the message is NOT marked read or archived
  (§7 error handling: agent/send failure does not mark read)."""
  imap, smtp, agent = _make_clients("<p>Hello.</p>")
  smtp.reply_email = AsyncMock(side_effect=RuntimeError("smtp boom"))
  await _process_one(imap, smtp, agent, "1")
  smtp.reply_email.assert_awaited_once()
  imap.mark_message.assert_not_awaited()
  imap.move_message.assert_not_awaited()
```

This is tight: behavior-based, fills the one real gap in the P3-002
acceptance matrix (the "on send failure, does not archive" cell),
reuses the existing `_make_clients` helper, no over-mocking. The
`monkeypatch` parameter in the signature is unused — drop it to keep the
signature minimal.

### Addition 2: explicit ordering assertion — APPROVED, with a tighter form

The existing `test_process_one_valid_reply_sends_html_then_marks_and_archives`
asserts each of `reply_email` / `mark_message` / `move_message` was
awaited, but not the order. Adding order is valuable — the §7 contract is
"send → mark → archive" and a regression that swapped mark-before-send
would currently slip past.

The plan's proposed snippet re-stubs all three mocks inside the test body
with `side_effect=lambda *a, **kw: calls.append(...)`. That works but is
verbose and discards the `_make_clients` setup. The tighter form keeps
the existing stubs and wraps just the three methods to record order:

```python
async def test_process_one_valid_reply_sends_html_then_marks_and_archives() -> None:
  """Branch 4: valid HTML → reply_email with html_body + mark read + archive,
  in that order (send → mark → archive per §7)."""
  imap, smtp, agent = _make_clients("<p>Hello.</p>")

  order: list[str] = []
  smtp.reply_email.side_effect = lambda *a, **kw: order.append("reply")
  imap.mark_message.side_effect = lambda *a, **kw: order.append("mark")
  imap.move_message.side_effect = lambda *a, **kw: order.append("archive")

  await _process_one(imap, smtp, agent, "1")

  assert order == ["reply", "mark", "archive"]

  call = smtp.reply_email.call_args
  assert call.kwargs["to"] == "owner@example.com"
  assert call.kwargs["subject"] == "Re: Hi"
  assert call.kwargs["body"] == ""
  assert call.kwargs["html_body"] == "<p>Hello.</p>"
  assert call.kwargs["in_reply_to"] == "<orig@example.com>"
```

Notes for the implementer:
- `AsyncMock`'s `side_effect` can be a sync callable — AsyncMock awaits
  the result if it's a coroutine, otherwise returns it. A sync lambda
  appending to a list is fine and is the standard pattern.
- Drop the existing separate `mark_message.assert_awaited_once_with(...)`
  / `move_message.assert_awaited_once_with(...)` lines only if the order
  list plus the `call.kwargs` block fully cover what they asserted. The
  order list covers "was called and in order"; keep the
  `assert_awaited_once_with` on `mark_message` / `move_message` if you
  want to also lock the exact args (the current test does). A minimal
  diff is to add the `order` list and the single `assert order == [...]`
  line, and leave the existing `assert_awaited_once_with` lines in place
  — that is the smallest change that closes the gap.

### Over-testing check

No over-testing found in either addition:
- The send-failure test asserts *what did not happen* (no mark, no
  archive) — that's the contract, not implementation.
- The ordering test asserts the §7-documented sequence — that's
  behavior, not internal call shape.
- Neither test reaches into private state or asserts on mock call counts
  beyond the contract.

## TDD stubs for the implementer

Both additions are small enough that the implementer can write them
directly as passing tests (no `pytest.fail` stub phase needed) — the
production code already supports these behaviors. The TDD "stub that
fails" pattern is for not-yet-implemented behavior; here the behavior
exists and the tests are locking it. Treat the two code blocks above as
the executable specifications: drop them into `tests/test_loop.py`
verbatim (minus the unused `monkeypatch` parameter on the send-failure
test), run `make test`, expect green.

## Summary

| Item | Decision |
|---|---|
| Q1 (a) vs (b) | **(b)** — no new test file; add one test to `tests/test_loop.py` |
| P3-001 net change | Add `test_build_message_omits_instructions_block`; flip checkbox |
| P3-002 send-failure test | Approved; drop unused `monkeypatch` fixture |
| P3-002 ordering assertion | Approved; use the tighter `side_effect` + `order` list form above |
| New file `tests/test_handoff.py` | Do NOT create |
| Blocked-on-bug in proposed plan | The `endswith("instructions:")` assertion is a tautology — must not ship |

Relevant files:
- `/Users/xtof/Workspace/agentic/yoker-assistant/tests/test_loop.py` (target of both additions)
- `/Users/xtof/Workspace/agentic/yoker-assistant/reporting/bucket-a-hardening/plan.md` (plan under review)