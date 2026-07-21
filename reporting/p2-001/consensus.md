# P2-001 Consensus — Port the Assistant Agent Definition

**Task:** P2-001 — Port the assistant agent definition (`agents/assistant.md` from `../c3/agents/assistant.md`)
**Reviewers:** security-engineer (tools frontmatter), functional-analyst (content port plan)
**Verdict:** APPROVED — proceed to implementation, with one task-sequencing question for the owner (S1 below).

## Wrapper Check

Passes trivially. P2-001 ports a markdown agent definition file. No wrapper classes, no indirections, no adapters proposed. The `tools:` frontmatter is data, not a class.

## Design Consensus

### Owner's TODO spec adopted as-is (with justified additions)

The TODO prescriptively lists what to keep, remove, and rework. The functional-analyst identified 5 additional sections needing rework beyond the TODO's explicit list — each justified by a specific stale reference (removed tool name, removed concept, dropped skill's artifact, impossible instruction in the email model), NOT by preference. This respects the Simplicity Principle.

### Tools frontmatter (security-engineer verified)

The bounded yoker tool set — all 12 names verified against yoker's actual tool registry:
- 10 yoker built-ins: `read`, `list`, `search`, `write`, `update`, `websearch`, `webfetch`, `skill`, `agent`, `git`
- 2 plugin tools: `pkgq:find` (confirmed: `__yoker_name__ = "find"` in pkgq plugin, NOT `pkgq:find_package`), `yoker_assistant:md_to_html` (P2-008, not yet implemented)

`git` supports read + commit + push with layered guardrails (no shell, arg sanitization, PathGuardrail, operation allowlist, permission gate, credential redaction).

### Section-by-section port plan

See `analysis/agent-definition-port-plan.md` for the full section-by-section table. Summary:

**Keep verbatim (6 sections):** `# Assistant Agent` intro, `## Key Responsibilities`, `## Categorization Rules`, `## Memory Integration`, `## Memory Instructions`, `## Personalization` (including "When Sending Emails" — still relevant since the agent's reply IS emailed by Python).

**Remove (4 items):** frontmatter `color`, `### Email Operations` section, guardrail item 6 "Use MCP tools for email", `### Skill Priority` table.

**Rework — TODO-explicit (3):** `tools:` frontmatter → bounded yoker set; Phase 2 Process → email = next user message (no file iteration); Phase 3 Reply → markdown → `md_to_html` (no outbox files).

**Rework — functional-analyst identified (5, each justified by stale reference):**
1. `## Tool Instructions` — c3 tool names (Read/Glob/Grep/Write/Edit) being renamed to yoker names; removed concepts (inbox files, session-state.md, outbox files). The line-59 PERSONAL.md read instruction is load-bearing and preserved.
2. Phase 1 Initialize — contains `Bash(pwd)` (Bash removed); reframe as the one-time session-setup turn (P1-004's `await agent.process(_INITIALIZE_PROMPT)`).
3. Phase 4 Update — references `session-state.md` (pa-session dropped per P2-004); stale. Memory-file update kept; PERSONAL.md write + `yoker:git` commit made explicit.
4. `## Output Format` — templates say "reply in inbox/" (impossible; only channel is email) and report `Inbox: Empty / Outbox: N files` (no filesystem inbox/outbox). Template structure kept; filesystem references removed.
5. `## Error Handling` — "Archive conflict" row references a filesystem archive the agent no longer performs (Python owns email archive). Other three rows kept.

### References to eliminate

All confirmed in the c3 source:
- `Bash`: tools list + `Bash(pwd)` in Phase 1
- `mcp__`: tools list + guardrail + Email Operations section
- `inbox/`: 5 occurrences across Tool Instructions, Process, Output Format
- `outbox/`: 3 occurrences across Tool Instructions, Reply, Output Format
- `archive` (agent-side): Error Handling row + Email Operations (removed with the section)

### PERSONAL.md preservation — confirmed

Read instruction preserved in reworked Tool Notes + Phase 1. Personalization section kept verbatim. Phase 4 makes the write (`yoker:update`) + commit (`yoker:git`) explicit to surface the TODO's "permits writing to it" and the §4.3 demo beat.

## Security Findings

| ID | Finding | Severity | Disposition |
|---|---|---|---|
| S1 | `yoker_assistant:md_to_html` declared but not yet implemented (P2-008 pending) → yoker logs missing-tool warning → P2-001 acceptance "no missing-tool warnings" cannot be met | Low | **Owner decision — task-sequencing question (see below)** |
| S2 | `git push --force` in git schema, gated by permission | Low | Accept for showcase; future yoker hardening |
| S3 | websearch/webfetch on untrusted email content | Low | Accept for showcase (same shape as P1-004 F1/F3); `domain_allowlist` is post-showcase mitigation |
| S4 | PERSONAL.md write + commit on untrusted content | Low | Accepted (P1-004 F4, demo beat) |
| S5 | pkgq:find errata in functional.md §3.2/§3.3 | Informational | P2-001 corrects it in the same edit |

No blocking findings. No guard beyond the owner's spec.

## ⚠️ Task-sequencing question for the owner (S1)

The P2-001 acceptance criterion "yoker logs no missing-tool warnings" conflicts with declaring `yoker_assistant:md_to_html` in the tools frontmatter before P2-008 lands (the tool is not yet implemented; `__YOKER_MANIFEST__ = PluginManifest(tools=[])` today).

Three options:
- **(A) Land P2-008 before P2-001 acceptance** — implement the `md_to_html` tool first, then P2-001's acceptance test passes cleanly. Reorders the backlog slightly.
- **(B) Relax P2-001 acceptance** — allow the one missing-tool warning until P2-008 lands. Pragmatic; the warning is cosmetic. P2-008 resolves it.
- **(C) Add `yoker_assistant:md_to_html` in P2-008 instead of P2-001** — P2-001's tools frontmatter lists 11 tools (not 12); P2-008 adds the 12th. Keeps acceptance clean but splits the tools frontmatter across two tasks.

No security impact either way. The owner decides.

## Errata riding this PR

- `analysis/functional.md` §3.2 and §3.3: `pkgq:find_package` → `pkgq:find` (the TODO already notes this errata).