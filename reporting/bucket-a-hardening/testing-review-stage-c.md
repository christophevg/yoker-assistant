# Stage c — Testing Review (Bucket A Hardening)

Reviewer: testing-engineer
Mode: Stage c quality review (post-implementation)
Scope: `tests/test_loop.py` additions for P3-001 (handoff contract) and P3-002 (send-failure + ordering).

## Verdict: APPROVE

The implementation matches the Phase 3 approved design on every checked
item, with one justified deviation in the send-failure test that fixes a
bug in my Phase 3 snippet (the approved version would have raised
uncaught). All 48 tests pass; `make check` is green; `loop.py` coverage
holds at 94%.

## 1. Phase 3 design alignment

| Item | Status | Evidence |
|---|---|---|
| Option (b): no `tests/test_handoff.py` created | ✅ | `ls tests/test_handoff.py` → not found |
| Tautology assertion dropped | ✅ | `test_build_message_omits_instructions_block` (lines 72-88) uses only the per-line `startswith` loop; no `endswith("instructions:")` tautology, no redundant case-sensitive substring check |
| Send-failure test: `monkeypatch` fixture dropped | ✅ | Signature is `async def test_process_one_send_failure_does_not_archive() -> None:` — no `monkeypatch` parameter |
| Ordering assertion: `side_effect` lambdas + shared `order` list | ✅ | Lines 217-224: shared `order: list[str] = []`, three `side_effect=lambda *a, **kw: order.append(...)` lambdas, `assert order == ["reply", "mark", "archive"]` |

## 2. Coverage results

`make test-cov` on `feature/bucket-a-hardening`:

```
src/yoker_assistant/loop.py    97    5    22    2    94%   170-172, 183, 194-195, 199->177
TOTAL                         193   20    56    4    90%
48 passed
```

Missing lines are all in `run()`, not `_process_one` or `build_message`:
- 170-172: `NotImplementedError` branch for Windows signal handlers.
- 183: `if stop.is_set(): break` mid-iteration escape.
- 194-195: `disconnect` exception swallow in the `finally`.
- 199->177: branch from end-of-iteration back to loop top.

None of these are in scope for P3-001/P3-002 (handoff contract +
per-message error propagation). The new send-failure test exercises the
previously-uncovered "exception propagates out of branch 4" path; the
ordering test adds branch-4 sequencing coverage. Coverage did not drop.

## 3. Test meaningfulness

### `test_build_message_omits_instructions_block` — real contract, not tautology

The assertion `for line in out.splitlines(): assert not
line.lower().startswith("instructions:")` would fail if anyone
reintroduced an `Instructions:` header line in `build_message`'s output.
That is the P3-001 regression contract. The body is verbatim, so a
malicious *user* body starting a line with `Instructions:` would also
trip the test — but the test's input body is `"Give me a status update."`
which contains no such line, so the test isolates the contract: "the
function itself does not emit an Instructions: header." Meaningful.

### `test_process_one_send_failure_does_not_archive` — deviation is a bug fix

The developer wrapped the call in `pytest.raises(RuntimeError,
match="smtp boom")`. My Phase 3 snippet did NOT include this wrapper:

```python
# Phase 3 approved (buggy):
await _process_one(imap, smtp, agent, "1")  # would raise uncaught
smtp.reply_email.assert_awaited_once()
imap.mark_message.assert_not_awaited()
imap.move_message.assert_not_awaited()
```

Looking at `_process_one` (loop.py lines 117-125): `smtp.reply_email` is
`await`ed directly with no try/except. A `RuntimeError` from it
propagates out of `_process_one`. Without `pytest.raises`, the test
would crash at the `await` line and never reach the `assert_not_awaited`
checks. The developer's deviation is **correct and necessary** — it
fixes a bug in my Phase 3 design. The docstring also correctly
documents the propagation target (`run()`'s per-message `except`
block), which matches the §7 contract. Approved.

The post-raise assertions (`mark_message.assert_not_awaited`,
`move_message.assert_not_awaited`) are still meaningful: they verify
that the exception short-circuited the mark/archive calls — i.e., the
"on send failure, does not archive" contract is locked.

### Tightened ordering test — routing assertions preserved

Lines 226-234 still assert the full `call.kwargs` routing contract:
- `to == "owner@example.com"`
- `subject == "Re: Hi"`
- `body == ""`
- `html_body == "<p>Hello.</p>"`
- `in_reply_to == "<orig@example.com>"`
- `mark_message.assert_awaited_once_with("1", "INBOX", "\\Seen", action="add")`
- `move_message.assert_awaited_once_with("1", "INBOX", "Archive")`

The tightening added the `order` list without dropping any existing
routing assertion. Good.

## 4. Edge cases

### `build_message` instructions contract

The test covers the case where the function does NOT emit an
Instructions header. It does not cover:
- A body whose content legitimately starts a line with `Instructions:`
  (false-positive risk). Out of scope: the contract is about what
  `build_message` adds, not what the body contains. The body is
  verbatim by design (P2-006).
- Case variants like `INSTRUCTIONS:` or `  instructions:` (leading
  whitespace). The `.lower().startswith("instructions:")` catches
  case but not leading whitespace. A header line in `build_message`'s
  output is always `Key: value` with no leading whitespace (see the
  f-string at line 69), so this is not a realistic regression vector.

No gaps that warrant a new test.

### `_process_one` error paths

The send-failure test covers `smtp.reply_email` raising in branch 4.
Not covered (and out of P3-002 scope):
- `imap.fetch_message` raising (propagates to `run()`'s per-message
  handler; the loop-continuation test at line 354 covers the
  run-level catch generically).
- `imap.mark_message` raising after a successful send (would leave
  the message read but not archived; not in the §7 matrix).
- `agent.process` raising (covered at run-level by
  `test_run_continues_after_process_one_exception`).

The §7 acceptance matrix cell "on send failure, does not archive" is
the one the new test fills. The other error paths were not in scope.

## 5. `make check` gate

```
All checks passed!
============================== 48 passed in 1.42s ==============================
```

48/48 tests pass. Format-check, lint, typecheck, test all green.

## Summary

The implementation is a faithful, tight execution of the Phase 3
approved design. The one deviation (`pytest.raises` on the send-failure
test) is a correct fix for a bug in my Phase 3 snippet — the developer
caught it and the docstring accurately documents the propagation
behavior. Coverage holds at 94% on `loop.py`; the new tests exercise
the branch-4 exception path and the send→mark→archive ordering without
dropping any existing routing assertion. No new file created, no
tautology shipped, no over-mocking, no fixture bloat.

Relevant files:
- `/Users/xtof/Workspace/agentic/yoker-assistant/tests/test_loop.py` (lines 72-88, 209-234, 237-250)
- `/Users/xtof/Workspace/agentic/yoker-assistant/src/yoker_assistant/loop.py` (lines 117-125 — branch 4 propagation)
- `/Users/xtof/Workspace/agentic/yoker-assistant/reporting/bucket-a-hardening/testing-design-review.md` (Phase 3 design this review compares against)