# Security Review (scoped) — P2-001 final ported `agents/assistant.md`

**Stage:** project-review Stage b, scoped re-verification
**Scope:** the implemented `/Users/xtof/Workspace/agentic/yoker-assistant/agents/assistant.md` (272 lines) against the Phase 3 approved tools frontmatter (`analysis/security-agent-definition-port.md`) and the consensus (`reporting/p2-001/consensus.md`).
**Reviewer:** security-engineer
**Verdict:** **APPROVED**

---

## 1. Tools frontmatter — exact match

The implemented frontmatter (lines 5–24) declares exactly the 12 approved tools, using the fully-qualified `yoker:` namespace form (which is how yoker's registry actually keys them — the `yoker` plugin source namespaces its built-ins via `__YOKER_MANIFEST__`, and `agent` is session-injected with `namespace="yoker", name="agent"` per `yoker/session/__init__.py:430-434`).

| # | Declared in file | Approved set | Match |
|---|---|---|---|
| 1 | `yoker:read` | `read` (yoker built-in) | yes |
| 2 | `yoker:list` | `list` | yes |
| 3 | `yoker:search` | `search` | yes |
| 4 | `yoker:write` | `write` | yes |
| 5 | `yoker:update` | `update` | yes |
| 6 | `yoker:websearch` | `websearch` | yes |
| 7 | `yoker:webfetch` | `webfetch` | yes |
| 8 | `yoker:skill` | `skill` | yes |
| 9 | `yoker:agent` | `agent` | yes |
| 10 | `yoker:git` | `git` (full git: read + commit + push) | yes |
| 11 | `pkgq:find` | `pkgq:find` (plugin) | yes |
| 12 | `yoker_assistant:md_to_html` | `yoker_assistant:md_to_html` (P2-008 pending) | yes |

**No extra tools. No missing tools.** Count = 12, matching the approved set exactly.

## 2. `pkgq:find` (not `find_package`) — confirmed

A targeted grep for `find_package` in the file returns **zero hits**. The only pkgq reference is `pkgq:find` at line 22. The errata correction from Phase 3 §2 is correctly applied in the implemented file.

## 3. No `Bash`, no `mcp__` — confirmed

- `grep -ciE "Bash" agents/assistant.md` → **0** hits. No `Bash`, no `Bash(pwd)`, no shell-access phrasing. This is the single largest blast-radius reducer and it is preserved.
- `grep -niE "mcp__" agents/assistant.md` → **0** hits. No MCP email-tool references. The agent cannot touch the mailbox directly; Python owns the email loop.
- Stale c3 references also absent: `grep -niE "inbox/|outbox/|session-state" agents/assistant.md` → **0** hits. The c3 filesystem-inbox/outbox model and `session-state.md` are fully removed.

## 4. No new instructions expanding the blast radius

The agent-definition body instructs the agent to perform only:

- Read `PERSONAL.md`, project `CLAUDE.md`, memory files (via `yoker:read`) — line 41, 81
- Read email content delivered by Python (no filesystem inbox) — lines 90-93
- Write/update TODO.md and memory files (via `yoker:write`/`yoker:update`) — lines 95-99, 115
- Invoke `pa-inbox` / `pa-outbox` skills (via `yoker:skill`) — lines 67-69
- Convert markdown reply to HTML (via `yoker_assistant:md_to_html`) — line 107
- Write learned behaviours to `PERSONAL.md` + commit/push (via `yoker:update` + `yoker:git`) — lines 117-120

Every instructed operation maps to a declared, guardrailed tool. No instruction directs the agent to perform a file or network operation outside the bounded tool set. No `mkdir`, no `existence`, no `make` (correctly excluded per Phase 3 §7).

## 5. PERSONAL.md write + git commit/push — explicit, accepted demo beat

Phase 4 (lines 113-120) makes the PERSONAL.md write (`yoker:update`) + git commit/push (`yoker:git`) explicit. This is the demo beat accepted in P1-004's `security-agent-seam.md` finding F4 and re-accepted in Phase 3 §5 / finding S4. No change to the boundary; same PathGuardrail, same git arg sanitization, same write/update content-size limits.

## 6. Owner's option B acknowledgment — confirmed

Consensus S1: the owner chose **option B** — relax P2-001 acceptance so the one missing-tool warning for `yoker_assistant:md_to_html` is allowed until P2-008 lands. The implemented file declares `yoker_assistant:md_to_html` in the frontmatter (line 23) and instructs its use in Phase 3 (line 107). This matches option B exactly: **declaration kept, missing-tool warning accepted.** The tool, when implemented in P2-008, has the smallest possible blast radius (markdown string in, HTML string out, no FS, no network — per Phase 3 §7). No security impact.

## 7. Owner's `md_to_html` reuse instruction — P2-008 concern, not P2-001

The owner noted `c3/bin/md-to-html.py` already exists and should be reused in P2-008. The P2-001 file does not prejudice the P2-008 implementation: it only declares the tool name and invokes it. No implementation details, no algorithm choice, no path assumptions are baked into the agent definition. P2-008 is free to reuse `c3/bin/md-to-html.py` or implement fresh. Confirmed.

## 8. Wrapper Check — passes trivially

P2-001 ports a markdown agent definition. No wrapper classes, no indirections, no adapters. The `tools:` frontmatter is data, not a class. Passes.

## 9. Security regressions vs Phase 3 — none

| Phase 3 finding | Status in implemented file |
|---|---|
| S1 (`md_to_html` declared, not yet implemented) | Present as declared; owner accepted option B. No regression. |
| S2 (`git push --force` in schema, deployment-config) | Unchanged — tool-level concern, not frontmatter. No regression. |
| S3 (websearch/webfetch on untrusted email) | Unchanged — bounded by yoker web guardrails. No regression. |
| S4 (PERSONAL.md write on untrusted content) | Unchanged — accepted demo beat. No regression. |
| S5 (`pkgq:find` errata) | Correctly applied: `pkgq:find`, not `pkgq:find_package`. No regression. |

No new findings. No new attack surface introduced by the port.

## 10. Positive observations

- **Zero `Bash` references** in the entire 272-line file — the showcase's central safety thesis is preserved.
- **Zero `mcp__` references** — the agent-as-IMAP attack surface is eliminated.
- **Zero stale c3 filesystem references** (`inbox/`, `outbox/`, `session-state.md`) — the port is clean.
- **Fully-qualified `yoker:` namespace** used consistently — matches yoker's actual registry keys, avoiding any bare-name resolution ambiguity at agent load.
- **Tool instructions stay within the bounded set** — every instructed operation maps to a declared tool.
- **PERSONAL.md demo beat made explicit** in Phase 4 (lines 117-120) — surfaces the security-relevant behaviour rather than hiding it in prose.

---

## Verdict

**`approved`** — the implemented `agents/assistant.md` tools frontmatter matches the Phase 3 approved set exactly (12 tools, no more, no less, no `Bash`, no `mcp__`, `pkgq:find` not `find_package`). No security regressions. Owner's option B (declare `yoker_assistant:md_to_html`, accept the missing-tool warning until P2-008) is correctly reflected. Owner's `md_to_html` reuse instruction is not prejudiced — P2-008 retains implementation freedom.