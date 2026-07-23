# P2-002 / P2-003 Evaluation — pa-inbox & pa-outbox Concepts

**Date:** 2026-07-23
**Status:** Evaluation complete. Conclusion: no changes to `assistant.md` or
new skill sub-workflows are warranted. Both tasks can be marked done.

## 1. Scope

Per the owner's directive, P2-002 and P2-003 are NOT ports — they are
evaluations of the old `../c3/skills/pa-inbox/SKILL.md` and
`../c3/skills/pa-outbox/SKILL.md` concepts against the new
`src/yoker_assistant/agents/assistant.md` agent definition (ported in
P2-001). The optional directive: "split off parts of the agent definition
into on-demand `yoker:skill` sub-workflows to simplify it."

This document records, per concept: applies / already handled / does not
apply, and a yoker:skill feasibility assessment.

## 2. yoker:skill Feasibility (can we ship skill sub-workflows?)

**Yes, the mechanism exists and is fully usable.** Confirmed against
`yoker/src/yoker/plugins/manifest.py`, `loader.py`, and
`core/__init__.py`:

- `PluginManifest(skills_dir="skills")` tells the plugin loader to
  discover `skills/*.md` from the package.
- Plugin skills are registered with the package namespace
  (`yoker_assistant:<skill>`).
- A `yoker:skill` tool is registered when skills are present and
  `config.tools.skill.enabled` (default True).
- A one-time skill discovery block is injected at session setup listing
  available skills (`context/manager.py:add_skill_discovery_block`).
- The agent invokes a skill on-demand via the `yoker:skill` tool; the
  skill's content is injected as a user-level `<skill>` message.

**The yoker-assistant package currently declares NO `skills_dir`** —
`__YOKER_MANIFEST__` sets only `tools=[md_to_html]` and
`agents_dir="agents"`. Adding `skills_dir="skills"` and shipping
`src/yoker_assistant/skills/*.md` would work with no code changes.

**So the question is not "can we?" but "should we?"** The answer below is
no, for the concepts under evaluation.

## 3. Per-Concept Classification

### 3.1 pa-inbox concepts

| Concept | Classification | Reason |
|---|---|---|
| Item categorization rules (actionable / needs clarification / cross-cutting / information) | **ALREADY HANDLED** | `assistant.md` lines 168-195 ("Categorization Rules": Project Detection, Clarity Assessment, Cross-Cutting Items) ported verbatim in P2-001. Core reasoning on every email. |
| Project detection (explicit prefix, context clues, known projects) | **ALREADY HANDLED** | `assistant.md` lines 170-175. |
| Clarity indicators (clear vs unclear criteria) | **ALREADY HANDLED** | `assistant.md` lines 177-188. |
| Memory integration (when to create, types, format) | **ALREADY HANDLED** | `assistant.md` lines 196-225 ("Memory Integration" section) plus the "Memory Instructions" section lines 274-283. |
| File I/O: list `inbox/`, move to `inbox/archive/`, write `outbox/` files | **DOES NOT APPLY** | Python owns mail transport; the agent does not manage an inbox directory. Documented in `functional.md` §3.4 (pa-inbox row). |
| `re-` threaded reply naming | **DOES NOT APPLY** | Email threading via `in_reply_to=` is owned by the loop (`loop.py` branch 4). Documented in `functional.md` §3.4. |
| "Update session state" step | **DOES NOT APPLY** | yoker's persistent context manager carries session state. Documented in `functional.md` §3.4 (pa-session dropped). |
| YAML frontmatter parsing of inbox files | **DOES NOT APPLY** | The inbox is an email, not a file with frontmatter. The handoff payload (`loop.build_message`) delivers From/Subject/Date + body only. |

### 3.2 pa-outbox concepts

| Concept | Classification | Reason |
|---|---|---|
| Reply format (Actions Taken table, Memory Created, Status, Pending Questions) | **ALREADY HANDLED** | `assistant.md` lines 227-254 ("Output Format": Processing Summary + Clarification Request templates). |
| Clarification vs resolution reply types | **ALREADY HANDLED** | The Clarification Request template (lines 244-254) and the categorization rules' "Unclear" branch cover this. |
| Writing reply files to `outbox/` | **DOES NOT APPLY** | The reply is `Agent.process()`'s return value (HTML); Python emails it. Documented in `functional.md` §3.4 (pa-outbox row). |
| Archive management (move originals) | **DOES NOT APPLY** | The loop archives the email (`imap.move_message`). |
| Markdown-to-HTML conversion | **ALREADY HANDLED** | The `yoker_assistant:md_to_html` tool (P2-008) converts the agent's markdown reply to HTML; the agent calls it in Phase 4: Reply. |
| Threading (`Re:` subject, `in_reply_to`) | **ALREADY HANDLED** | The loop constructs `subject=f"Re: {subject}"` and `in_reply_to=msg["message_id"]` (`loop.py` branch 4). |
| HTML safety guardrail | **ALREADY HANDLED** | The loop's `_contains_unsafe_html` guard (`loop.py` lines 42-51) catches `<script>`/`<style>`/`<img>`/`<iframe>`/`<object>`/`<embed>`/`<form>` and `on*=` handlers. |
| Inline reply processing (user prefix lines) | **DOES NOT APPLY** | A c3-file-convention for threaded clarification rounds; email replies are native threading, no prefix parsing. |
| Action/Memory table column specs | **ALREADY HANDLED** | Captured in the Output Format templates in `assistant.md`. |

## 4. Skill Sub-Workflow Split Assessment

The owner's directive: "Optionally split off parts of the agent definition
into on-demand `yoker:skill` sub-workflows to simplify it." Evaluated
against each candidate section of `assistant.md`:

| Section | On-demand? | Split warranted? |
|---|---|---|
| Categorization Rules | No — core reasoning on every email | **No.** Moving always-relevant reasoning behind a `yoker:skill` invocation adds tool-call overhead and a "forgot to invoke" risk. The agent would have to call the skill every turn. This is the opposite of simplification. |
| Memory Integration | No — applies whenever memory is created, which is a common per-email outcome | **No.** Same reasoning. |
| Output Format (reply templates) | No — every reply uses these templates | **No.** The agent composes a reply on every turn; a skill invocation per turn is pure overhead. |
| Phase 1: Initialize bootstrap (PERSONAL.md missing) | Yes — conditional, runs only when PERSONAL.md is missing | **Marginal / No.** This is the only genuinely optional path. But it is tightly coupled to reading PERSONAL.md (the agent's first action), already conditional in the definition, and ~40 lines. Splitting it into a `bootstrap` skill adds: a `skills/` directory, a manifest field, a skill file, and an invocation step — for a rare path that is already self-contained. Net complexity increases. |
| Guardrails / Error Handling / Personalization | No — always-relevant context | **No.** |

**Conclusion of the split assessment:** no split is warranted. The
content that is always relevant (categorization, memory, reply format,
guardrails) must stay in the agent definition to avoid per-turn skill
invocations. The one conditional path (bootstrap) is already slim and
self-contained; splitting it adds indirection for no gain.

The yoker skill mechanism is designed for on-demand specialized
workflows (e.g., `/commit`, `/git-activity-report`) — not for factoring
out an agent's core always-on reasoning. Using it for the latter would
misuse the mechanism and violate the Simplicity Principle (indirection
without behavior gain).

## 5. Recommended Plan

**No changes to `assistant.md`. No new skill sub-workflows. No changes
to `__YOKER_MANIFEST__`.**

Rationale:

1. Every applicable pa-inbox and pa-outbox concept is already present in
   `assistant.md` (ported in P2-001) or already handled by the loop /
   the `md_to_html` tool / yoker's persistent context manager.
2. The concepts that do not apply are already documented as removed in
   `functional.md` §3.4.
3. Splitting always-relevant content into `yoker:skill` sub-workflows
   would add per-turn tool-call overhead and a "forgot to invoke" risk
   — the opposite of simplification.
4. The one conditional path (bootstrap) is already slim and
   self-contained; a skill split adds indirection for no behavior gain.

## 6. Task Closure

- **P2-002:** Mark done. The evaluation is documented (this file); no
  skill sub-workflow split is warranted; the agent definition needs no
  simplification here. Acceptance criteria met: "the evaluation is
  documented (which concepts apply, which don't, and why); any skill
  sub-workflow split off from the agent definition loads under
  `yoker:skill`" — vacuously satisfied (no split needed).
- **P2-003:** Mark done. Same rationale. Acceptance criteria met
  vacuously (no split needed).

## 7. Cross-Reference

- `functional.md` §3.4 — the pa-inbox/pa-outbox porting verdicts
  (KEPT / REMOVED / DROPPED) that this evaluation confirms and refines.
- `assistant.md` — the ported agent definition containing all
  applicable concepts.
- `loop.py` — owns threading, HTML guardrail, archive, and the
  four-way reply branch (concepts that moved out of the agent).