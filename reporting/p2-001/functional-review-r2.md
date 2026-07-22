# P2-001 Functional Review — Round 2 (PR #5 round-1 feedback)

**Reviewer:** functional-analyst
**Scope:** Verify round-1 changes to `agents/assistant.md` (Item A — channel-agnostic rework) and `TODO.md` (Item B — P2-002/P2-003 reframing) satisfy the owner's round-1 comments and that P2-001 acceptance criteria still pass.

---

## Item A — Channel-agnostic rework

### Owner's comment (quoted verbatim, inline at line 87)

> "I'm not sure if the (pre-) loop is relevant to the agent. From its point of view, it is in a dialog with the user. The fact that this dialog is managed by a Python loop is "external" to its own world. The only fact it should know is that the dialog is happening using email, so it should reply using an HTML body. If in the near future the loop will for example also include checking instant messages, this agent's work doesn't change. It will respond similar to both email and instant messages replies. So I think we need to avoid focussing on the external factors here. This agent's focus is on accepting unstructured input from the human user (whatever the channel may be), interpreting that input, acting upon it and responding to it in an unstructured manner."

### Does the rework satisfy it?

Yes. The agent definition now speaks in terms of "user messages" and "turns" throughout the workflow phases, not emails/poll loops/Python plumbing. The only transport facts retained are the ones the owner explicitly carved out as the agent's business: the reply channel is email (so the reply body is HTML), and the user-facing email preferences live in PERSONAL.md ("When Sending Emails", "Tone/style guidelines for emails", "Email formatting, workflow preferences"). All external-loop plumbing references (pre-loop, poll loop, `Agent.process(_INITIALIZE_PROMPT)`, "delivered by Python", "Python emails it verbatim", "inbox directory", "email content (From/Subject/Date + body)") are gone.

### Forbidden-reference grep

```
$ grep -nE "pre-loop|poll loop|Agent\.process|smtp\.reply_email|delivered by Python|Python emails|inbox directory|email content \(From" agents/assistant.md
(none)
```

### Remaining "email" references (all in the preserved categories)

| Line | Reference | Category |
|------|-----------|----------|
| 4 | "process my email" example phrase | (c) owner-preserved example phrase |
| 100 | "Tone/style guidelines for emails" | (b) PERSONAL.md bootstrap question (reply channel is email) |
| 103 | "When Sending Emails" PERSONAL.md section name | (b) user-facing email preferences |
| 117 | "When Sending Emails" PERSONAL.md section name | (b) user-facing email preferences |
| 301 | "## When Sending Emails" PERSONAL.md section | (b) user-facing email preferences |
| 310 | "Email formatting, workflow preferences, etc." | (b) PERSONAL.md Behaviors example |
| 317 | "Email formatting, workflow preferences" | (b) PERSONAL.md Behaviors example |

Every remaining "email" reference is either (a) the preserved transport fact (HTML reply via `yoker_assistant:md_to_html` — the conversion call at lines 104 and 161 is the operational expression of "reply using an HTML body"), (b) user-facing email preferences in PERSONAL.md, or (c) the "process my email" example phrase. None of them re-introduce the external-loop framing the owner objected to.

### Simplicity Principle check (Item A)

The rework is subtractive — rewording and removing transport-specific phrasing — not additive. No new abstractions, no wrappers, no indirections, no new sections. The agent definition is the same shape and length as before, just with channel-agnostic wording. Satisfies the simplicity default.

---

## P2-001 acceptance criteria (re-verified)

| Criterion | Status |
|-----------|--------|
| `Agent(agent_path="agents/assistant.md")` loads | Pass — frontmatter is valid YAML; structure intact |
| 12 declared tools all resolve (no missing-tool warnings) | Pass — `yoker:read`, `yoker:list`, `yoker:search`, `yoker:write`, `yoker:update`, `yoker:websearch`, `yoker:webfetch`, `yoker:skill`, `yoker:agent`, `yoker:git`, `pkgq:find`, `yoker_assistant:md_to_html` (lines 7-23). Count = 12. |
| `pkgq:find` (not `pkgq:find_package`) | Pass — line 22 declares `pkgq:find`; grep confirms `pkgq:find_package` absent |
| No `mcp__` references and no `Bash` | Pass — grep returns none |
| No forbidden c3-specific sections (Email Operations, "Use MCP tools for email" guardrail, skill-priority table, `color:` frontmatter) | Pass — grep returns none |
| Definition instructs reading PERSONAL.md at session start | Pass — line 41 ("Read PERSONAL.md first") and lines 78-79 (Phase 1 step 1) |
| Definition permits writing to PERSONAL.md | Pass — lines 114-119 (Phase 1 step 5, `yoker:write`) and line 144 (Phase 3 step 3, `yoker:update`) |

All P2-001 acceptance criteria still pass after the round-1 rework.

---

## Item B — TODO.md P2-002 / P2-003 reframing

### Owner's comment (quoted verbatim)

> "I quickly reviewed pa-inbox and pa-outbox. I believe both are rather "old", because they focus on the old way the old assistant operated using an inbox folder and files in that folder. This was before it had access to an actual email account. So, I think that porting those skills will be more like evaluating the concepts captured in there and consider any of them to be applicable to the new assistant agent's definition, to improve that and not really port those skills. The TODO phase/task for porting them, might be use to evaluate them and optionally split off skills from the new agent definition, to simplify it and to separate optional paths in the workflow into on-demand skill sub-workflows. To be considered at that time."

### Does the update satisfy it?

Yes. P2-002 (TODO.md lines 195-211) and P2-003 (lines 213-229) are reframed:

- Both titles now read "Evaluate pa-inbox/pa-outbox concepts and optionally split off skill sub-workflows" (not "port the skill").
- Both open with "**NOT a port.**" and explain the old skill targets the old file-folder workflow, before the assistant had a real email account.
- Both call out the evaluate-and-apply concept: "Evaluate the concepts captured in it ... and consider which are applicable to the new assistant agent's definition to improve it."
- Both include the optional split-off: "Optionally, split off parts of the new agent definition into on-demand skill sub-workflows to simplify it and to separate optional paths in the workflow into on-demand skill sub-workflows."
- Both include the deferral: "**To be considered at that time** — this task is in the backlog; the evaluation happens when this task is picked up, not now."
- Acceptance criteria updated to match: evaluation documented; any split-off skill loads under `yoker:skill`; agent definition simplified where applicable.

### Simplicity Principle check (Item B)

The TODO update is a direct implementation of the owner's guidance — no extra process, no new artifacts, no wrappers. The reframing replaces "port" with "evaluate" and adds the optional split-off language verbatim from the owner's comment. Satisfies the simplicity default.

---

## Verdict

**approved**

- Item A: all forbidden transport references removed; the 7 remaining "email" references are each in one of the three owner-preserved categories; the rework is subtractive, not additive. The owner's "the agent is in a dialog with the user, the Python loop is external" framing is now reflected in the wording.
- Item B: P2-002 and P2-003 are reframed from port to evaluate-and-optionally-split, with the deferral "to be considered at that time" carried through.
- All P2-001 acceptance criteria still pass: 12 tools resolve, `pkgq:find` (not `find_package`), no `mcp__`/`Bash`, no c3-specific sections, PERSONAL.md read at session start and write permitted.