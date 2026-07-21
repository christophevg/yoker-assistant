# Agent Definition Port Plan — P2-001

Source: `/Users/xtof/Workspace/agentic/c3/agents/assistant.md` (322 lines)
Target: `/Users/xtof/Workspace/agentic/yoker-assistant/agents/assistant.md`

This plan covers EVERY section of the c3 source. The TODO spec (P2-001,
`TODO.md` lines 157–191) explicitly lists some sections; for the rest, the
Simplicity Principle applies — the owner's TODO is the default, and any
rework I propose beyond it is justified below by a specific problem
(stale reference to a removed concept).

## Owner's Instructions (quoted verbatim from TODO P2-001)

> **Keep** concept, workflow phases (Initialize → Process → Reply →
>   Update), categorization rules, memory/personalization guidance.
> **Keep** the PERSONAL.md read/write behaviour AS-IS from c3: the
>   definition instructs the agent to read `PERSONAL.md` at session start
>   (via `yoker:read`) AND to write learned behaviours to it (via
>   `yoker:update`/`yoker:write`) for later.
> **Remove** the entire "Email Operations" section, the "Use MCP tools
>   for email" guardrail, the c3-specific skill-priority table, and the
>   `color` frontmatter field.
> **Rework** the `tools:` frontmatter to the bounded yoker set: `read`,
>   `list`, `search`, `write`, `update`, `websearch`, `webfetch`, `skill`,
>   `agent`, `git` (**full git**: read + commit + push), `pkgq:find`,
>   and `yoker_assistant:md_to_html` (the custom local tool from P2-008).
> **ERRATA (pkgq tool name — api-architect review of P1-002):** the
>   published `pkgq` yoker plugin exposes its package-finder tool as
>   **`pkgq:find`**, NOT `pkgq:find_package`. ... Use `pkgq:find` in the
>   `agents/assistant.md` `tools:` frontmatter.
> Rewrite the "Process" and "Reply" phases to fit the persistent-session
>   email handoff: each email is the next user message in an ongoing
>   session; the reply is composed in markdown then converted to HTML via
>   the `md_to_html` tool; no outbox files.

Acceptance criteria (quoted):

> `Agent(agent_path="agents/assistant.md")` loads; declared tools all
> resolve (yoker logs no missing-tool warnings — in particular
> `pkgq:find` resolves; `pkgq:find_package` would NOT resolve and must
> not appear); the definition contains no `mcp__` references and no
> `Bash`; the definition instructs reading `PERSONAL.md` at session start
> and permits writing to it.

## Does the plan satisfy each quoted item?

- "Keep concept, workflow phases, categorization rules, memory/personalization guidance" — YES. All four sections are kept (rows below).
- "Keep PERSONAL.md read/write AS-IS" — YES. Personalization section (lines 285–322) kept verbatim; the read instruction at line 59 is preserved in the reworked Tool Instructions; the Phase 1 read is preserved.
- "Remove Email Operations, MCP guardrail, skill-priority table, `color`" — YES. All four removed (rows below).
- "Rework tools: frontmatter to bounded yoker set with pkgq:find + yoker_assistant:md_to_html" — YES. See frontmatter port table.
- "Rewrite Process and Reply phases for persistent-session email handoff" — YES. See phase rework detail.
- Acceptance "no mcp__ references, no Bash" — YES. See references-to-eliminate list.
- Acceptance "PERSONAL.md read at session start + permits writing" — YES. See preservation confirmation.

## Section-by-Section Table

| Section | Lines | Verdict | What changes | Why |
|---|---|---|---|---|
| Frontmatter `name` | 2 | KEEP | — | yoker agent-definition field. |
| Frontmatter `description` | 3–4 | KEEP | Optional light trim of "process my inbox" example (the inbox is now email, not a directory) — non-load-bearing. | Concept kept per TODO. |
| Frontmatter `color` | 5 | REMOVE | Delete line. | TODO explicit. Claude Code UI hint; yoker does not use it. |
| Frontmatter `tools:` | 6–41 | REWORK | Replace entire list with the bounded yoker set (see frontmatter port table). | TODO explicit + pkgq:find errata. |
| `# Assistant Agent` + intro | 44–46 | KEEP | — | Concept. |
| `## Key Responsibilities` | 48–53 | KEEP | — | Concept; "Maintain Session State" is still true (now via persistent context manager, not a file). |
| `## Tool Instructions` | 55–94 | REWORK | Replace per-tool subsections (Read/Glob/Grep/Write/Edit/Skill) with a compact "Tool Notes" block. PRESERVE the line-59 instruction "Read PERSONAL.md first" (load-bearing). Remove references to `inbox/` files, `session-state.md`, `outbox/` files, `inbox/*.md` glob. Update the `Skill` subsection's skill list: drop `pa-session` (dropped per P2-004), keep `pa-inbox` and `pa-outbox` (reworked). | TODO does not address this section. Problem: the subsections reference c3 tool names (Read, Glob, Grep, Write, Edit) that are being renamed to yoker names, AND reference removed concepts (inbox files, session-state.md from the dropped pa-session skill, outbox files). yoker's tools are self-documenting via guardrails; per-tool prose for the built-ins adds no value. The PERSONAL.md read instruction is the one load-bearing line and must survive. Skill list must reflect the reworked skill set. |
| `## Workflow` Phase 1: Initialize | 97–104 | REWORK | Remove `Bash(pwd)` (line 102) and the "determine your working directory" step (line 100–101) — yoker agents run with a configured working directory, no pwd needed. Keep "Read PERSONAL.md from the current directory". Reframe the phase as the ONE-TIME session-setup turn: triggered by the loop's `await agent.process(_INITIALIZE_PROMPT)` before the poll loop begins (P1-004 / §4.1), NOT repeated per email. | TODO says rework Process and Reply but does not explicitly mention Initialize. Problem: `Bash` is removed from the tool set (TODO explicit) so `Bash(pwd)` cannot remain; the "determine working directory" step is a c3-orchestrator concept that does not apply to a yoker SDK agent with a configured cwd. The email-handoff model (§4.1) makes Initialize a one-time startup turn, so the phase must say so to avoid the agent re-initializing per email. |
| `## Workflow` Phase 2: Process | 106–118 | REWORK | Replace "For each file in inbox" framing with "For each email (the next user message in the ongoing session)". Keep the categorization (Actionable → TODO.md / Unclear → clarification / Cross-cutting → agentic TODO / Information → memory file). Keep "Execute actions (create projects, update TODOs)". Remove the file-iteration framing. | TODO explicit. |
| `## Workflow` Phase 3: Reply | 120–128 | REWORK | Replace "Generate outbox reply" with "Compose the reply in markdown, then call `yoker_assistant:md_to_html` to convert it to HTML; the HTML string is the reply body (Python emails it verbatim)". Remove "Archive processed files" (Python owns archive). | TODO explicit ("reply in markdown → md_to_html; no outbox files"). |
| `## Workflow` Phase 4: Update | 130–136 | REWORK | Remove "Update session-state.md" (line 133). Keep "Create/update memory files" and "Update memory index". Optionally add "Write learned behaviours to PERSONAL.md (via `yoker:update`) and commit via `yoker:git`" to make the TODO's "permits writing to it" explicit and surface the §4.3 demo beat. | TODO does not explicitly mention Phase 4. Problem: `session-state.md` is pa-session's artifact, and pa-session is dropped (P2-004 / §3.4). The reference is stale and must be removed. The persistent context manager carries session state; the agent's update job is memory files + PERSONAL.md learned behaviours. Keeping the memory-file update; adding the PERSONAL.md write makes the TODO's "permits writing" instruction visible in the definition. |
| `## Categorization Rules` | 138–164 | KEEP | — | TODO explicit (categorization rules kept). |
| `## Memory Integration` | 166–195 | KEEP | — | TODO explicit (memory guidance kept). Memory files are written via `yoker:write`; the format template is reusable as-is. |
| `## Output Format` | 197–227 | REWORK | Keep the Processing Summary and Clarification Request template structures. Remove the `**Inbox:** Empty` / `**Outbox:** N files` lines (no filesystem inbox/outbox). Remove "Please reply in inbox/ with your clarifications" — replace with "Reply via email with your clarifications" (clarifications come back as the next email, per §4.1). | TODO does not explicitly mention this section. Problem: the templates reference `inbox/` and `outbox/` directories that do not exist in the email-handoff model (§2.1, §3.4 pa-inbox rework). "Reply in inbox/" is impossible — the user's only channel is email. The template structure is useful; the filesystem references are stale. |
| `## Guardrails` items 1–5 | 229–235 | KEEP | — | General guardrails; none reference inbox/outbox/MCP. Item 2 "Archive files, don't remove them" is a general principle and stays (the agent still creates memory/TODO files; "archive" here is conceptual, not the email archive which Python owns). |
| `## Guardrails` item 6 | 236 | REMOVE | Delete the item. | TODO explicit ("Use MCP tools for email" guardrail removed). |
| `### Skill Priority` | 238–247 | REMOVE | Delete the subsection. | TODO explicit (c3-specific skill-priority table). The referenced c3 skills (`c3:git-activity-report`, `c3:project-status`, `c3:commit`) do not exist in yoker-assistant. |
| `### Email Operations` | 249–263 | REMOVE | Delete the subsection. | TODO explicit. Email operations moved to Python (§3.4 pa-email removed). |
| `## Error Handling` | 265–272 | REWORK | Remove the "Archive conflict | Preserve both versions" row (archive is Python's job now). Keep "Project not found", "TODO.md missing → Create with template", "Ambiguous item → Add to clarification list". | TODO does not explicitly mention this section. Problem: the "Archive conflict" row references a filesystem archive operation the agent no longer performs (Python archives emails; the agent never touches the email archive). The other three rows are still valid (agent still creates/updates project TODO.md files via `yoker:write`). |
| `## Memory Instructions` | 274–283 | KEEP | — | TODO explicit (memory guidance kept). `memory/` directory and types (project/feedback) still applicable — agent writes memory files via `yoker:write`. |
| `## Personalization` | 285–322 | KEEP | — | TODO explicit (PERSONAL.md read/write AS-IS). The "When Sending Emails" subsection (tone/style) is still relevant — the agent's reply IS sent as an email by Python, so tone guidance applies. Keep verbatim. |

## Phase Rework Detail

### Phase 1: Initialize (one-time session-setup turn)

The c3 phase runs at the start of every invocation. In the yoker-assistant
model (§4.1, P1-004), Initialize is run ONCE: the loop sends
`await agent.process(_INITIALIZE_PROMPT)` before the poll loop begins, and
the agent reads `PERSONAL.md` on that first turn. Subsequent emails are
the next user messages in the same session — Initialize is NOT repeated.

Reworked content (paraphrase, not final prose):

1. This phase runs ONCE at session startup (the loop delivers an
   explicit initialize prompt before the poll loop begins).
2. Read `PERSONAL.md` from the current working directory (via `yoker:read`)
   to establish identity and learned behaviours for the ongoing session.
3. Do not re-initialize per email — each email is the next user message
   in the same session.

Removed: `Bash(pwd)` and the "determine your working directory" step
(yoker agents run with a configured cwd).

### Phase 2: Process (per-email reasoning)

Reworked content:

1. Each incoming email is the next user message in the ongoing session
   (delivered by Python; no inbox directory).
2. Read the email content (From/Subject/Date + body).
3. Categorize each item:
   - Actionable → Add to the relevant project's TODO.md (via `yoker:write`/`yoker:update`)
   - Unclear → Add a clarification question to the reply
   - Cross-cutting → Track as an agentic-level TODO
   - Information → Create a memory file (via `yoker:write`)
4. Execute actions (create projects, update TODOs, write memory).

Kept: categorization rules, action execution. Removed: "For each file in
inbox" file-iteration framing.

### Phase 3: Reply (markdown → HTML, no outbox)

Reworked content:

1. Compose the reply in markdown following the Output Format templates
   (Actions Taken, Questions Remaining, Memory Created, Status).
2. Call `yoker_assistant:md_to_html` to convert the markdown reply to HTML.
3. The HTML string is the reply body — `Agent.process()` returns it and
   Python emails it verbatim.

Removed: "Generate outbox reply file", "Archive processed files". The
reply is the agent's text output, not a file; Python owns archive.

### Phase 4: Update (memory + PERSONAL.md, no session-state.md)

Reworked content:

1. Create/update memory files (via `yoker:write`/`yoker:update`).
2. Update the memory index.
3. Write learned behaviours to `PERSONAL.md` (via `yoker:update`) when
   the user expresses a preference or a workflow pattern is discovered;
   commit and push via `yoker:git` (full git).

Removed: "Update session-state.md" (pa-session dropped, P2-004; the
persistent context manager carries session state). Added: explicit
PERSONAL.md write + git commit to surface the TODO's "permits writing"
instruction and the §4.3 demo beat.

## Frontmatter Port: `tools:`

| c3 tool | yoker-assistant tool | Verdict |
|---|---|---|
| `Read` | `yoker:read` | KEPT (renamed) |
| `Glob` | `yoker:list` | REWORKED (yoker has `list`, not a separate Glob) |
| `Grep` | `yoker:search` | REWORKED |
| `Skill` | `yoker:skill` | KEPT (renamed) |
| `Write` | `yoker:write` | KEPT (renamed) |
| `Edit` | `yoker:update` | KEPT (renamed; yoker's edit tool is `update`) |
| `WebSearch` | `yoker:websearch` | KEPT (renamed) |
| `WebFetch` | `yoker:webfetch` | KEPT (renamed) |
| `Bash` | — | REMOVED (yoker safety model: no open shell) |
| `AskUserQuestion` | — | REMOVED (no interactive UI; clarifications go in reply text) |
| `PushNotification` | — | REMOVED (no UI) |
| `ListMcpResourcesTool` | — | REMOVED (MCP-specific) |
| `ReadMcpResourceTool` | — | REMOVED (MCP-specific) |
| `mcp__plugin_c3_email__*` (10 tools) | — | REMOVED (email loop moved to Python) |
| `mcp__plugin_c3_pkgq__find_package` | `pkgq:find` | REWORKED (yoker plugin; ERRATA correction — NOT `pkgq:find_package`) |
| `Agent` | `yoker:agent` | KEPT (renamed; 1 level of sub-agents preserved) |
| (new) | `yoker:git` | ADDED (full git: read + commit + push; §4.3 demo beat) |
| (new) | `yoker_assistant:md_to_html` | ADDED (custom local tool, P2-008) |

Final bounded `tools:` list for `agents/assistant.md`:

```yaml
tools:
  - yoker:read
  - yoker:list
  - yoker:search
  - yoker:write
  - yoker:update
  - yoker:websearch
  - yoker:webfetch
  - yoker:skill
  - yoker:agent
  - yoker:git
  - pkgq:find
  - yoker_assistant:md_to_html
```

`pkgq:find` (NOT `pkgq:find_package`) per the TODO erratum. The
`functional.md` §3.2/§3.3 references to `pkgq:find_package` are errata
to correct in the same P2-001 edit (TODO lines 177–180).

## References to Eliminate

All of the following must NOT appear in the ported
`agents/assistant.md` (acceptance: "no `mcp__` references and no
`Bash`"; the inbox/outbox/archive references are stale per the
email-handoff model):

### `Bash`
- Line 19: `Bash` in the `tools:` list — removed by frontmatter port.
- Line 102: `Use Bash(pwd) to determine the absolute path` — removed by Phase 1 rework.

### `mcp__`
- Lines 24–25: `ListMcpResourcesTool`, `ReadMcpResourceTool` — removed (MCP support tools).
- Lines 27–37: `mcp__plugin_c3_email__*` (10 entries) — removed by frontmatter port.
- Line 39: `mcp__plugin_c3_pkgq__find_package` — replaced by `pkgq:find`.
- Line 236: guardrail "Use MCP tools for email" — removed (TODO explicit).
- Lines 249–263: `### Email Operations` section (references MCP email tool ordering) — removed (TODO explicit).

### `inbox/` (and `inbox` filesystem references)
- Line 60: "Read inbox files to process" — removed by Tool Instructions rework.
- Line 67: "List inbox files: `inbox/*.md`" — removed by Tool Instructions rework.
- Line 109: "For each file in inbox" — removed by Phase 2 rework.
- Line 211: `**Inbox:** Empty` — removed by Output Format rework.
- Line 226: "Please reply in inbox/ with your clarifications" — removed/rewritten by Output Format rework.

### `outbox/` (and `outbox` filesystem references)
- Line 78: "Create outbox reply files" — removed by Tool Instructions rework.
- Line 123: "Generate outbox reply with:" — removed by Phase 3 rework.
- Line 212: `**Outbox:** N files` — removed by Output Format rework.

### `archive` (agent-side archive references; Python now owns email archive)
- Line 127: "Archive processed files" — removed by Phase 3 rework.
- Line 232: guardrail "Archive files, don't remove them" — KEPT (this is a general principle about not deleting source files; the word "archive" here is conceptual, not the email Archive folder. Not a stale reference. If the implementer judges it confusing alongside Python-owned email archive, it may be reworded to "Don't delete originals; preserve them" — non-load-bearing.)
- Line 260: "move_email → Move to Archive folder" — inside Email Operations, removed with the section.
- Line 265 (Error Handling): "Archive conflict | Preserve both versions" — removed by Error Handling rework.

## PERSONAL.md Read/Write Preservation (Confirmation)

The TODO requires the PERSONAL.md read/write behaviour be kept AS-IS from
c3. Confirmation:

- **Read at session start:** the line-59 instruction "Read PERSONAL.md
  first — Start every session by reading your personal configuration" is
  PRESERVED in the reworked Tool Notes section. The Phase 1 Initialize
  instruction "Read PERSONAL.md from the current directory" is PRESERVED
  (reframed as the one-time session-setup turn).
- **Write learned behaviours:** the Personalization section (lines
  285–322) is KEPT VERBATIM, including the "Behaviors — Learned
  behaviors (self-learning section)" template and the "Where to store
  learned information" table row "Behavioral instructions → PERSONAL.md
  → Behaviors". The Phase 4 Update rework makes the write explicit
  ("Write learned behaviours to PERSONAL.md via `yoker:update`; commit
  and push via `yoker:git`") — this surfaces the TODO's "permits
  writing to it" instruction in the definition and matches the §4.3
  demo beat. The write mechanism changes from c3's `Edit`/`Write` to
  yoker's `yoker:update`/`yoker:write` (frontmatter port), but the
  read/write BEHAVIOUR is identical: read at startup, write learned
  behaviours for later.

## Wrapper Check

P2-001 proposes no wrapper classes. The task creates a markdown file
(`agents/assistant.md`) from another markdown file. No Python classes,
no indirection layers, no forwarding methods. Passes the Wrapper Check
trivially.

## Simplicity Principle — Justification for Reworking Sections the TODO Did Not Explicitly Address

The TODO explicitly addresses: frontmatter `tools:`, `color`, Email
Operations, MCP guardrail, skill-priority table, Process phase, Reply
phase, PERSONAL.md read/write. The TODO does NOT explicitly address:
Tool Instructions (55–94), Phase 1 Initialize (97–104), Phase 4 Update
(130–136), Output Format (197–227), Error Handling (265–272). For each,
the rework is justified by a specific stale-reference problem, not
personal preference:

- **Tool Instructions:** references c3 tool names (Read/Glob/Grep/Write/Edit)
  being renamed AND removed concepts (inbox files, session-state.md,
  outbox files). If kept as-is, the definition would instruct the agent
  to use tools it does not have and to read files that do not exist. The
  one load-bearing line (PERSONAL.md read) is preserved.
- **Phase 1 Initialize:** contains `Bash(pwd)`. `Bash` is removed (TODO
  explicit), so `Bash(pwd)` cannot remain. The "determine working
  directory" step is a c3-orchestrator concept. The email-handoff model
  (§4.1) makes Initialize a one-time startup turn; without rework the
  agent would believe it re-initializes per email.
- **Phase 4 Update:** references `session-state.md`, which is pa-session's
  artifact. pa-session is dropped (P2-004, §3.4). The reference is stale.
- **Output Format:** templates say "reply in inbox/" (impossible — the
  only channel is email) and report `Inbox: Empty / Outbox: N files`
  (filesystem state that does not exist). The template structure is
  useful; the filesystem references are stale.
- **Error Handling:** the "Archive conflict" row references a filesystem
  archive operation the agent no longer performs (Python owns email
  archive). The other three rows are still valid and kept.

No rework is proposed for sections the TODO says to keep (concept, Key
Responsibilities, Categorization Rules, Memory Integration, Guardrails
1–5, Memory Instructions, Personalization). The owner's proposal is the
default; these are kept as-is.