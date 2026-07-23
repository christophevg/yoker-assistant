# P2-005 + P2-006 Summary

Date: 2026-07-23

## Task

Combined P2-005 (main loop) + P2-006 (handoff payload builder) per owner instruction: "Combine P2-005 and P2-006 into one PR, because 006 is 'merely' a function, so don't make it any bigger than that."

## What was implemented

- **loop.py**: async run() with C1 whitelist startup guard, Agent constructed once with Persisted(SimpleContextManager()), IMAP/SMTP directly, four-way _process_one branching (sentinel/empty/guard-fail/valid), build_message pure function with CR/LF collapse, _contains_unsafe_html 7-tag denylist guardrail, SIGINT/SIGTERM graceful shutdown, --once flag
- **__main__.py**: thin CLI (argparse + asyncio.run)
- **handoff.py**: DELETED (residue from overengineered design)
- **agents/assistant.md**: +5 lines Step 0 ({{NO_REPLY}} sentinel instruction in Phase 4)
- **tests/test_loop.py**: 29 tests (build_message, _contains_unsafe_html, four-way branching, C1 guard, exception isolation)
- **analysis/functional.md**: §4.3 and §7 updated

## Plan evolution

- R0: initial plan (two open decisions)
- R1: owner approved HTML guardrail + empty-reply option (b); added sentinel
- R2: functional-analyst proposed leave-UNSEEN for guard failures; owner rejected
- R3: reverted to mark-read-no-archive for guard failures; notice to original sender; owner approved

## Review results

| Stage | Agent | Verdict |
|-------|-------|---------|
| a | functional-analyst | approved |
| b | api-architect | approved |
| b | security-engineer | approved |
| c | code-reviewer | approved |
| c | testing-engineer | approved (round 1 — 2 tests added) |
| e | make check | 44 tests pass |

## Wrapper Check

PASS. No wrapper classes. Agent, IMAPClient, SMTPClient constructed directly. build_message is a plain function. Helpers are plain functions. run() is earned multi-step orchestration.

## Owner simplicity directives (all satisfied)

1. "Combine P2-005 and P2-006 into one PR" — one PR, one implementation
2. "006 is 'merely' a function" — build_message is a 16-line plain function in loop.py
3. "the split handoff-builder still is a residu from an overengineered previous design" — handoff.py deleted
4. "please consider simplicity" — no wrapper classes, no sub-wrappers, no over-engineering
