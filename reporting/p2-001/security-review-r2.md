# Security Review R2 — P2-001 (assistant.md port, PR #5 round-1 feedback)

**File:** `agents/assistant.md` (317 lines)
**Round:** 2 (scoped re-run, Stage b security — channel-agnostic rework verification)
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

No additions, removals, or renames. Identical to round 0/round 1.

### 2. No forbidden references — PASS

Grep for `Bash | mcp__ | inbox/ | outbox/ | pkgq:find_package | session-state.md` returned zero hits (exit 1). No shell-tool exposure, no MCP-prefixed tools, no filesystem inbox/outbox paths, no session-state file, no `pkgq:find_package` rename.

### 3. Channel-agnostic rework introduced no new tool references — PASS

The rewording removed transport-specific framing but introduced no new tool references. The only tool references in the body are backtick-quoted calls to declared tools:

- `yoker:read` (line 79)
- `yoker:write` (lines 115, 132, 135, 142)
- `yoker:update` (lines 132, 142, 144)
- `yoker:git` (lines 119, 146, 159)
- `yoker_assistant:md_to_html` (lines 104, 161)

All five referenced tools are in the declared set of 12. No undeclared tool calls. The other seven declared tools (`yoker:list`, `yoker:search`, `yoker:websearch`, `yoker:webfetch`, `yoker:skill`, `yoker:agent`, `pkgq:find`) are not invoked in the body text — they remain available to the agent at runtime without being prescribed.

### 4. No security regressions vs round 0 — PASS

Frontmatter tool list matches round 0 exactly (see check 1). File length dropped from 321 to 317 lines via the channel-agnostic rework; the reduction is prose trimming, not tool-surface change.

### 5. Option B preserved — PASS

`yoker_assistant:md_to_html` is declared (line 23) and referenced (lines 104, 161) but not yet implemented — pending P2-008. The runtime missing-tool behavior is unchanged from round 1; the Phase 4: Reply error-surfacing guard (line 162, "do not swallow it") covers any failure.

### 6. P2-008 implementation freedom preserved — PASS

The rework preserves the tool contract as a pure `markdown → html` string transform at two call sites (bootstrap turn line 104, normal-reply line 161). No transport-specific framing was added that would constrain the implementation. P2-008 may still reuse `c3/bin/md-to-html.py` or implement independently — the agent definition imposes no filesystem or network side-effect requirements on the tool.

## Findings

None.

## Positive observations

- Tool surface stays bounded at 12 across all three rounds — no scope creep from the channel-agnostic rework.
- The rewording reduced file length without introducing any new tool calls.
- Error-surfacing guard (line 162) preserved — silent failures still prohibited.
- Guardrails retain "Never delete" / "Never modify original input" — source-data integrity preserved.
- No shell tool exposure means no command-injection surface via the agent definition.

## Scope classification

| Finding | Classification | Action |
|---------|---------------|--------|
| (none) | — | — |

## Recommendation

Approve. No security regressions, tools frontmatter unchanged, no new forbidden references, no new tool references introduced by the channel-agnostic rework.