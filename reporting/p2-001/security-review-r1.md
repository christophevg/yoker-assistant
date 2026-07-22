# Security Review R1 — P2-001 (assistant.md port, PR #5 feedback)

**File:** `agents/assistant.md` (321 lines)
**Round:** 0 (scoped re-run, Stage b security)
**Scope:** tools frontmatter + new PERSONAL.md bootstrap flow tool references
**Verdict:** approved

## Wrapper check
Trivially passes — markdown agent definition, no wrapper classes.

## Checks run

### 1. Tools frontmatter unchanged — PASS

The 12 bounded yoker tools declared in lines 5–24 are exactly:

1. `yoker:read`
2. `yoker:list`
3. `yoker:search`
4. `yoker:write`
5. `yoker:update`
6. `yoker:websearch`
7. `yoker:webfetch`
8. `yoker:skill`
9. `yoker:agent`
10. `yoker:git`
11. `pkgq:find`
12. `yoker_assistant:md_to_html`

No additions, removals, or renames relative to the Phase 3 list.

### 2. No forbidden references — PASS

Grep for `Bash | mcp__ | inbox/ | outbox/ | pkgq:find_package | session-state.md` returned zero hits. No shell-tool exposure, no MCP-prefixed tools, no filesystem inbox/outbox paths, no session-state file (replaced by the `PERSONAL.md` flow), no `pkgq:find_package` rename.

### 3. Bootstrap flow tool references — PASS

The new Phase 1: Initialize bootstrap flow (lines 79–125) references only declared tools:
- `yoker:read` (line 80)
- `yoker_assistant:md_to_html` (lines 106, 164)
- `yoker:write` (line 117)
- `yoker:git` (line 121)

Phase 2/3/4 references (`yoker:write`, `yoker:update`, `yoker:git`, `yoker_assistant:md_to_html`) all stay within the declared set. No new tool surface introduced.

### 4. No security regressions vs Phase 3 — PASS

Frontmatter tool list matches Phase 3 exactly (see check 1).

### 5. Option B preserved — PASS

`yoker_assistant:md_to_html` is declared (line 23) and referenced (lines 106, 164) but not yet implemented — pending P2-008. The missing-tool warning at runtime is accepted until P2-008 lands; the agent's Phase 4: Reply handles this turn and surface failures via the error-surfacing guard (line 162, "do not swallow it"). No security impact from the deferred implementation.

### 6. P2-008 implementation freedom — PASS

The bootstrap flow only invokes the tool as a markdown-to-HTML converter at two call sites. No constraints on the implementation shape are imposed by assistant.md — P2-008 may reuse `c3/bin/md-to-html.py` or implement it independently. The tool contract is a pure `markdown → html` string transform with no filesystem or network side effects referenced in the agent definition.

## Findings

None.

## Positive observations

- Tool surface stays bounded at 12 — no scope creep from the bootstrap flow addition.
- Error-surfacing guard (line 162) prevents silent failures in the new commit+push path.
- Guardrails retain "Never delete" / "Never modify original input" — preserves integrity of source data.
- No shell tool exposure means no command-injection surface via the agent definition.

## Scope classification

| Finding | Classification | Action |
|---------|---------------|--------|
| (none) | — | — |

## Recommendation

Approve. No security regressions, no new forbidden references, no tool-surface expansion.