# P1-004 Task Summary

**PR:** https://github.com/christophevg/yoker-assistant/pull/4
**Branch:** `feature/p1-004-agent-seam`
**Type:** Documentation-only / decision record (descoped from implementation)

## What was implemented

P1-004 was descoped per owner feedback during PR #4 plan review. The
`Assistant(agent_path)` wrapper class failed the Wrapper Check: it added no
behavior beyond `Persisted(...)` config in `__init__` and forwarded
`process()`/`setup()` unchanged to `Agent`. Same over-engineering pattern as
P1-003's `Mailbox` wrapper.

Owner chose **option A**: inline the `Persisted(...)` wiring in the loop
(P2-005's `__main__.py` / `loop.py`). No `agent.py` module. No `make_agent`
factory. No `Assistant` class. The "seam" is yoker's `Agent` itself.

P1-004 with option A delivers:
1. The `functional.md` §2.3 erratum (`PersistenceContextManager` → `Persisted`).
2. The swept TODO.md (P1-004, P2-005, P3-002, S-02 rewritten; 14 other
   entries reviewed and kept).
3. Descope addenda to the three analysis docs.
4. This decision record.

The actual `Agent` construction lands in P2-005 (the loop). P1-004 is now the
erratum + TODO sweep + decision record.

## Key decisions

- **Wrapper Check applied to the owner's own TODO spec.** The TODO proposed
  the `Assistant` wrapper; the cross-domain review adopted it as-is per
  "owner's proposal is the default"; the owner caught it in PR review. The
  gap: the Simplicity Gate fired on reviewer divergence, not on the owner's
  own proposal. Instruction update (Wrapper Check + re-rank "avoid wrappers"
  as primary) is a follow-up task.
- **TODO sweep.** The entire TODO.md was swept with the Wrapper Check. Four
  entries rewritten (P1-004, P2-005, P3-002, S-02). 14 entries reviewed and
  kept (earned behavior or no wrapper present). No ambiguous calls.
- **Option A chosen.** The slimmest option — no `agent.py` at all. The
  `Persisted(...)` wiring + `_SESSION_ID` + `_INITIALIZE_PROMPT` constants
  live wherever the loop lives (P2-005).

## Lessons learned

- The "owner's proposal is the default" framing makes the owner's own
  wrapper proposals immune to the wrapper/indirection check. The check only
  fires on reviewer recommendations that diverge from the owner's proposal.
  This is the same gap that caused P1-003's `Mailbox` wrapper to reach
  consensus before the owner caught it.
- The instruction update (Wrapper Check + re-ranking) is needed to prevent
  recurrence across future projects, not just this one.
- When the TODO contains detailed design proposals (written by
  functional-analyst in earlier sessions), those proposals can carry forward
  over-engineering patterns the owner already rejected in a previous round.
  The TODO needs a simplicity sweep after every descope, not just at initial
  creation.

## Files modified

- `analysis/functional.md` — §2.3 erratum
  (`PersistenceContextManager` →
  `Persisted(SimpleContextManager(), session_id="yoker-assistant")`).
- `TODO.md` — swept (P1-004, P2-005, P3-002, S-02 rewritten; 14 other
  entries reviewed and kept).
- `analysis/api-agent-seam.md` — descope banner added at top; original
  review preserved as historical record.
- `analysis/security-agent-seam.md` — descope banner added at top; original
  review preserved as historical record.
- `reporting/p1-004/consensus.md` — DESCOPE UPDATE section added at top;
  original consensus preserved as historical record.
- `reporting/p1-004/functional-review.md` — Stage a functional review
  (approved).
- `reporting/p1-004/summary.md` — this file.

## Security review outcome (carries over unchanged)

No blocking findings. No guard beyond the owner's spec.

Two Medium architectural risks accepted by design:
1. Prompt-injection persistence across emails in the single long-lived
   session.
2. On-disk session persistence across restarts.

Clean mitigation for both is a loop-level sender allowlist in P2-005 (if the
owner wants it later) — not a seam concern.
