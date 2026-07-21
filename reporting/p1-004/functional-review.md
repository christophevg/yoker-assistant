# Functional Review — P1-004 (Stage A)

**Task:** P1-004 — Agent construction + one-time session setup (option A: documentation-only descope)
**Reviewer:** functional-analyst
**Date:** 2026-07-21
**Commit reviewed:** `5db4d9d` (refactor: descope P1-004 to drop Assistant wrapper per owner feedback)

## Verdict

**APPROVED.** The documentation changes satisfy P1-004's revised acceptance
criteria (option A). No regressions. One minor observation (non-blocking) about
a conditional `make_agent` factory mention that hedges beyond the owner's
proposal — the default is inline, so it does not violate the Simplicity
Principle, but it could be tightened.

## Files reviewed

| File | Change | Verified |
|---|---|---|
| `analysis/functional.md` | §2.3 erratum (`Persisted` rename) | ✅ (landed in `2220ba4`, carried forward) |
| `TODO.md` | Swept: P1-004, P2-005, P3-002, S-02 rewritten; 14 others reviewed/kept; done entries + errata preserved | ✅ |
| `analysis/api-agent-seam.md` | Descope banner at top; original content preserved | ✅ |
| `analysis/security-agent-seam.md` | Descope banner at top; original content preserved | ✅ |
| `reporting/p1-004/consensus.md` | DESCOPE UPDATE section at top; original content preserved | ✅ |

The descope commit `5db4d9d` touched four files (TODO.md + the three analysis
docs). The `functional.md` §2.3 erratum was already applied in the earlier
P1-003 descope commit `2220ba4` and is still correct — no action needed in
this commit. All five deliverables are present in the tree.

## Findings

### 1. Erratum correctness (functional.md §2.3) — PASS

`analysis/functional.md` §2.3 (lines 109-114) shows:

```python
agent = Agent(agent_path="agents/assistant.md",
              context_manager=Persisted(SimpleContextManager(),
                                         session_id="yoker-assistant"))
```

This matches yoker 0.8.0's `Persisted(wrapped, storage_path=None,
session_id="auto")` signature: `SimpleContextManager()` as the positional
`wrapped` arg, `session_id="yoker-assistant"` as the keyword arg. The import
line (`from yoker import Agent, Persisted, SimpleContextManager`) is
consistent across all docs.

**No `PersistenceContextManager` occurrences remain in `functional.md`.** The
grep across `analysis/` and `reporting/` returned hits only inside the
historical-record sections of `api-agent-seam.md`, `security-agent-seam.md`
(quoted owner spec), and `consensus.md` — all explicitly preserved as
historical context with descope banners at the top. None are active
specifications. Correct.

### 2. TODO sweep correctness — PASS

- **P1-004 (lines 109-153):** States "No `Assistant` wrapper class" as the
  lead. The `Agent` is constructed directly with
  `Persisted(SimpleContextManager(), session_id="yoker-assistant")`. The
  one-time setup turn is `await agent.process(_INITIALIZE_PROMPT)` inlined in
  the loop. The historical `Assistant` design is retained as a "Note (original
  scope, retained for the historical record)" — correctly quarantined.
  Acceptance criteria say "no `Assistant` class exists in the package." ✅

- **P2-005 (lines 273-330):** Constructs `Agent` directly
  (`Agent(agent_path="agents/assistant.md",
  context_manager=Persisted(SimpleContextManager(),
  session_id="yoker-assistant"))`) with the explicit note "(per P1-004 — no
  `Assistant` wrapper)". The one-time setup is `await
  agent.process(_INITIALIZE_PROMPT)`. ✅

- **P3-002 (lines 385-406):** Stubs "a fake `Agent` (no backend — a stub that
  returns a canned reply string from `process()`)" — `Agent`, not
  `Assistant`. ✅

- **S-02 (lines 431-447):** "Implement as a Makefile target, not a Python
  wrapper module." Explicitly states "No Python class, no adapter, no façade —
  a Makefile recipe is the right-sized home." ✅

- **Done entries preserved:** P1-001 (line 14), P1-002 (line 26), P1-003 (line
  64) all carry their `✅` marks and historical/descope notes intact. ✅

- **Errata notes preserved:** P2-001 `pkgq:find_package` → `pkgq:find` errata
  (lines 172-180), P2-006 `EmailMessage` drop scope update (lines 340-347),
  P1-003 `Mailbox` descope (lines 64-105). ✅

- **Two-space indentation:** Sub-bullets use 2-space indent (`  - `).
  Continuation lines under sub-bullets use 4-space alignment with the text
  after the bullet marker — standard markdown list continuation, consistent
  with the TODO.md template in the system prompt. ✅

### 3. Descope addenda — PASS

- **`analysis/api-agent-seam.md`:** Line 1 has a blockquote DESCOPE NOTE
  explaining the wrapper was dropped (fails the Wrapper Check), the loop
  constructs `Agent` directly, and the content below is the historical review.
  Original review content preserved verbatim below. ✅

- **`analysis/security-agent-seam.md`:** Line 1 has a blockquote DESCOPE NOTE
  stating the security findings still apply (persistent-session architecture
  unchanged), only the wrapper class is gone. Original review content
  preserved. ✅

- **`reporting/p1-004/consensus.md`:** "## DESCOPE UPDATE" section at the top
  (lines 3-39) with the Wrapper Check rationale, the descope bullets, what
  still applies, and TODO.md state. Original consensus content preserved
  below the `---` separator (lines 41+). ✅

### 4. No regressions — PASS

The descope commit `5db4d9d` modified exactly four documentation files
(TODO.md, api-agent-seam.md, security-agent-seam.md, consensus.md) per `git
show --stat`. No `.py` files, no `Makefile`, no `pyproject.toml`, no test
files touched. The change is documentation-only — `make check` is trivially
unaffected. No code regressions possible from this commit.

## Simplicity Principle Check

**Owner's explicit proposal (quoted from the task):** "option A — inline in
the loop, no `agent.py`, no `Assistant` class, no `make_agent` factory."

| Owner's directive | Documentation state | Satisfied? |
|---|---|---|
| Inline in the loop | P1-004: "the two lines above live directly in `__main__.py`/`loop.py`" — primary path | Yes |
| No `agent.py` | P1-004: "`agent.py` either disappears entirely... or shrinks to module-level constants" — disappearance is the first option | Yes (with a hedge — see observation) |
| No `Assistant` class | P1-004, P2-005, P3-002 all explicitly state no `Assistant`; acceptance criteria enforce it | Yes |
| No `make_agent` factory | P1-004 mentions `make_agent` as a **conditional** option ("only warranted if the wiring grows past a one-liner; otherwise inline it") | Defaults to inline; see observation |

**Observation (non-blocking):** P1-004 (lines 126-132) mentions
`make_agent(agent_path) -> Agent` as a conditional fallback "only warranted if
the wiring... grows past a one-liner; otherwise inline it." The owner's
proposal excludes the factory outright. The TODO defaults to inline (matching
the owner) and gates the factory behind a growth condition that has not
triggered (the wiring is a one-liner). This is a hedge, not an active
reintroduction — no wrapper/indirection is proposed for the current
implementation. Flagging for awareness; no fix required for approval. If the
owner wants it tightened to match the proposal verbatim, one sentence can be
removed.

No `Assistant` class, no `Mailbox` analogue, no DI parameter, no
`setup(prompt=)` parameter, no `EmailMessage` dataclass, no sync wrapper, no
`close()`/context-manager protocol is reintroduced. The descope is clean.

## Summary

The documentation changes correctly reflect option A (inline `Agent`
construction in the loop, no wrapper class). The §2.3 erratum is applied. The
TODO.md sweep is internally consistent across P1-004, P2-005, P3-002, and S-02.
Done entries and historical errata are preserved. The three analysis docs
carry descope banners with original content preserved below. No code files
were touched, so no runtime regressions are possible. One minor hedge
(conditional `make_agent` mention) defaults to the owner's inline proposal
and does not block approval.