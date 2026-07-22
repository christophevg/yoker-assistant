# P2-005 + P2-006 Consensus

Date: 2026-07-22

## Reviewers
- api-architect: APPROVED (with spec errata corrections)
- security-engineer: APPROVED with 1 blocking fix (C1)

## Owner's simplicity directive (binding)
- "Combine P2-005 and P2-006 into one PR" — satisfied
- "006 is 'merely' a function, so don't make it any bigger than that" — satisfied: build_message is a plain function in loop.py
- "the split handoff-builder still is a residu from an overengineered previous design" — satisfied: no handoff.py module
- "please consider simplicity when implementing these two in one go" — satisfied: no wrapper classes, no sub-wrappers

## Consensus items

### Module structure (api-architect)
- __main__.py: thin CLI entry point (--once flag, asyncio.run(run()))
- loop.py: async run() + build_message() + helpers
- Delete handoff.py stub (residue from overengineered design)
- agent.py is also residue (P1-004's territory, not this PR)

### build_message (api-architect + security-engineer)
- Pure function in loop.py (not a separate module)
- Signature: build_message(email_message: dict) -> str
- Output: "From: ...\nSubject: ...\nDate: ...\n\n<body>"
- No instructions block
- Uses .get(..., "") defensively
- M2 fix: collapse CR/LF in the three header field values to prevent handoff-format injection

### run() (api-architect)
- Async. Constructs EmailAccount from env, Agent ONCE with Persisted(SimpleContextManager(), session_id="yoker-assistant")
- await agent.process(_INITIALIZE_PROMPT) once
- await imap.connect()
- SMTPClient constructed (no connect — fire-and-forget aiosmtplib.send per call)
- SIGINT/SIGTERM handlers on asyncio.Event
- Per iteration: search UNSEEN -> per-message _process_one -> --once breaks -> empty inbox sleeps poll_interval
- _process_one: fetch -> build_message -> reply_html = await agent.process(message) -> if non-empty: smtp.reply_email(...) -> mark read -> archive
- finally: imap.disconnect()

### SDK errata corrections (api-architect — REQUIRED)
1. SMTPClient has NO connect()/disconnect() — do NOT call them (functional.md §2.4 and TODO P2-005 are wrong on this)
2. reply_email(to=...) takes str, not list — TODO P2-005's `to=sender` is correct
3. reply_email requires body: str — loop must pass body="" (plain-text alt intentionally empty per §4.3)
4. move_message requires source folder: move_message(mid, "INBOX", "Archive")
5. Sender extraction: use email.utils.parseaddr(msg["from"])[1] to get bare address

### Security fixes (security-engineer)
- C1 (BLOCKING): startup check in run() — refuse to enter loop if get_recipient_whitelist().enabled is False (~6 lines). EMAIL_RECIPIENT_WHITELIST_ADDRESSES fails open by default; the whitelist is the primary reply-safety boundary.
- M2: build_message collapses CR/LF in header field values (~3 lines)

### Open decisions for owner (in implementation plan)
- M1: loop does not enforce that the agent called md_to_html. Options: (a) light loop-side guard for <script/<img/<style (~5 lines), (b) accept-and-document for demo scope. Security-engineer flags as owner decision.
- Empty-reply handling: when agent.process returns empty string. Options: (a) leave UNSEEN (risks infinite retry), (b) mark read + archive (treats as "agent chose not to reply"), (c) mark read only. api-architect recommends (b).

### Wrapper Check
PASS. Agent, IMAPClient, SMTPClient constructed directly. build_message is a plain function. Helpers are plain functions. The loop itself is earned multi-step orchestration. No wrapper classes, no sub-wrappers.

## Verdict
CONSENSUS REACHED. Proceed to Phase 5 (implementation plan + PR + owner approval gate).
