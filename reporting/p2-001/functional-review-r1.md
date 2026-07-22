# Functional Review — P2-001 PR #5 Round 0

**File:** `/Users/xtof/Workspace/agentic/yoker-assistant/agents/assistant.md` (321 lines)
**Round:** 0 (first feedback round, 5 inline owner comments)

## Owner-Feedback Verification

### Change 1 — Generic agent name placeholder

**Owner comment (line 253):** "Eira is too specific, replace with generic reference to the name of an agent."

**Implementation:** `## <Agent Name>` placeholder at lines 302 and 105 (PERSONAL.md template + bootstrap questions list).

**Satisfies?** Yes. The hardcoded "Eira" is gone; both the template and the bootstrap questions now use `## <Agent Name>` / "the agent's name (the `## <Agent Name>` slot)".

**Deviation:** None.

### Change 2 — Reorder Update before Reply

**Owner comment (line 118):** "git commit + push should also include recorded memories and be reported to the user. So I think Phase 4 should be before Phase 3. That way, the reply is really the last action and includes all previous actions, including any problems that might be experienced during those actions."

**Implementation:**
- Phase 3 is now **Update** (lines 142-153); Phase 4 is now **Reply** (lines 155-167).
- Update step 4 (line 149-150): commit+push via `yoker:git` includes "PERSONAL.md changes **and the memory-file writes performed in this phase**" — recorded memories are included in the commit.
- Update step 5 (line 151-152): errors are captured and surfaced, not swallowed.
- Reply step 2 (lines 160-163): explicitly reports "success or failure of the PERSONAL.md write, the memory-file writes, and the `yoker:git` commit+push. Any error encountered during Phase 3: Update is surfaced in the reply (not swallowed)."

**Satisfies?** Yes on all three sub-requirements: (a) commit includes recorded memories, (b) reply is last action, (c) problems are reported.

**Deviation:** None. Note: numbering shift (old Phase 3 Reply → new Phase 4 Reply; old Phase 4 Update → new Phase 3 Update) — this is exactly what the owner proposed ("Phase 4 should be before Phase 3").

### Change 3 — Generalize project-guidance mention

**Owner comment (line 241):** "Make this more general. This is merely to support other harnesses' guidance files... `AGENTS.md` is also a more general option. Also note that these are optional, in the sense that they might not be there."

**Implementation:** Three locations updated:
1. Personalization bullet (line 290): "Project guidance files (e.g. CLAUDE.md, AGENTS.md) — Project-specific guidance, if present (optional; these may not exist)"
2. read tool instruction (line 42): "Read project guidance files (e.g. CLAUDE.md, AGENTS.md) if present"
3. Project Detection (line 176): "Known projects from project guidance files (CLAUDE.md, AGENTS.md) if present"

**Satisfies?** Yes. AGENTS.md added, optionality made explicit (at least in the canonical Personalization bullet; the other two use "if present" which conveys optionality).

**Deviation:** None.

### Change 4 — Drop pa-inbox/pa-outbox sub-bullets

**Owner comment (line 68):** "These skills are currently missing from the PR."

**Implementation:** The `### skill` section (lines 65-67) now reads only "Invoke sub-skills for specialized tasks." — the pa-inbox/pa-outbox sub-bullets are gone.

**Satisfies?** Yes. The owner's observation was that those skills are not yet ported (P2-002/P2-003 own that work). Removing the forward references keeps P2-001 self-contained and consistent with the backlog structure. The owner did not prescribe a specific action; removing is the simplest alignment.

**Deviation:** None. (Owner comment was observational, not prescriptive; removal is the simplest interpretation consistent with the TODO.md where P2-002 and P2-003 own porting those skills.)

### Change 5 — PERSONAL.md bootstrap flow

**Owner comment (line 81):** "If PERSONAL.md is missing, the agent should start by generating one. To do this, it must send a mail to the user. This can be a reply to the initialise request from the pre-loop Python code. The mail should contain questions that the user needs to answer to allow the agent to construct its initial PERSONAL.md file. Some welcoming text, some guidance and the questions should be in that request for initialisation information. This also means that the initial mails will be going back and forth until the PERSONAL.md file can be fully constructed."

**Implementation (lines 86-125):**
- Step 3: bootstrap triggered when PERSONAL.md missing; reply to the initialise prompt from pre-loop Python `Agent.process(_INITIALIZE_PROMPT)` ✓
- Welcoming text (agent introduces itself) ✓
- Guidance on what PERSONAL.md is and why needed ✓
- Questions mapping to PERSONAL.md sections (Hello / Agent Name / When Sending Emails / Personal Goals / Behaviors) ✓
- HTML conversion via `yoker_assistant:md_to_html` ✓
- "Do NOT write PERSONAL.md yet — wait for the user's answers" ✓
- Step 4: iteration over email until enough info ✓
- Step 5: write initial PERSONAL.md via `yoker:write`, optionally commit+push via `yoker:git` ✓
- Step 6: normal flow resumes once PERSONAL.md exists ✓
- Error Handling note (line 273): "PERSONAL.md missing is NOT an error — it triggers the Phase 1: Initialize bootstrap flow" ✓

**Satisfies?** Yes. Every element of the owner's comment is addressed.

**Deviation:** None. Minor additive detail (optionally commit+push the bootstrap PERSONAL.md via `yoker:git`, and "Behaviors left empty or seeded with bootstrap-derived defaults") — these are reasonable extensions consistent with the existing Update-phase pattern and do not contradict the owner's proposal.

## Simplicity Principle — Wrapper Check

All 5 changes are markdown-only edits to an agent definition file. No wrappers, indirections, or code introduced. Wrapper Check passes trivially.

## P2-001 Acceptance Criteria

| Criterion | Status |
|---|---|
| `Agent(agent_path="agents/assistant.md")` loads (markdown structure intact) | PASS — valid YAML frontmatter, well-formed headings, no structural breakage |
| 12 bounded yoker tools in frontmatter resolve | PASS — all 12 present: `yoker:read`, `yoker:list`, `yoker:search`, `yoker:write`, `yoker:update`, `yoker:websearch`, `yoker:webfetch`, `yoker:skill`, `yoker:agent`, `yoker:git`, `pkgq:find`, `yoker_assistant:md_to_html` (lines 7-23) |
| `pkgq:find` resolves; `pkgq:find_package` must NOT appear | PASS — `pkgq:find` at line 22; `pkgq:find_package` grep returns zero |
| No `mcp__` references | PASS — grep zero |
| No `Bash` references | PASS — grep zero |
| PERSONAL.md read at session start | PASS — line 41 (read tool instruction), line 79-81 (Phase 1 step 1) |
| PERSONAL.md write permitted | PASS — Phase 1 step 5 (line 116-121 `yoker:write`), Phase 3 Update step 3 (line 147-148 `yoker:update`) |
| 4 c3-specific sections absent (color frontmatter, Email Operations, MCP guardrail, Skill Priority) | PASS — all four grep zero |
| `inbox/` / `outbox/` references | PASS — grep zero for both |
| `session-state.md` reference | PASS — grep zero |
| `pa-inbox` / `pa-outbox` references | PASS — grep zero |
| No regressions vs original port | PASS — workflow phases, categorization rules, memory integration, personalization all intact |

## Owner-Proposal Alignment Summary

| # | Owner proposal | Implemented as | Aligned? |
|---|---|---|---|
| 1 | Replace "Eira" with generic agent-name reference | `## <Agent Name>` placeholder | Yes |
| 2 | Phase 4 (Update) before Phase 3 (Reply); reply reports commit+memories+errors | Reordered; Reply reports Update outcome | Yes |
| 3 | Generalize to AGENTS.md; note optionality | 3 locations updated with AGENTS.md + "if present"/optional | Yes |
| 4 | (Observational) skills missing from PR | Removed forward references | Yes |
| 5 | Bootstrap flow: reply email, welcoming text, guidance, questions, iterate, then write | Full bootstrap flow in Phase 1 steps 3-6 | Yes |

## Result

**approved**

All 5 owner-feedback changes satisfy the inline PR comments without deviation, and all P2-001 acceptance criteria still pass. The markdown structure is intact, the 12 bounded yoker tools resolve in frontmatter, all forbidden references are absent, PERSONAL.md read/write is preserved, and the 4 c3-specific sections remain removed. No regressions introduced.