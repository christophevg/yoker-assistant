# Plan Revision R1 — Owner Feedback on PR #7 (P2-005 + P2-006)

**Date:** 2026-07-22
**Author:** Functional Analyst
**Scope:** Incorporate owner feedback on PR #7 into the implementation plan for
the combined P2-005 (main loop) + P2-006 (handoff payload builder) task.

## Owner's instructions (quoted verbatim)

> 1. YES! Do add a guardrail check in the loop, validating the produced HTML.
>    This is a very nice example of a structured guardrail added in the mix,
>    ensuring the output from the agent is not harmful to the user.
>
> 2. This should be option b) mark as seen and archive. I do think that we
>    should ask the agent to produce some exact feedback that clearly
>    indicates that it was its intention not to reply. Simply an empty reply
>    "could" also result from a problem. Making this explicit, allows the loop
>    to distinguish between "no reply" and "a problem" (in which case it can
>    simply try again).

## Does the revision satisfy each quoted item?

1. **"Do add a guardrail check in the loop, validating the produced HTML."**
   YES. A `_contains_unsafe_html(html)` function is added to `loop.py`. It
   runs on every non-empty, non-sentinel `agent.process()` return value
   before the reply is sent. If it returns True, the reply is NOT sent. See
   §1 below.

2. **"option b) mark as seen and archive"** (for intentional no-reply).
   YES. When the agent emits the no-reply sentinel, the loop marks the
   message `\Seen` and moves it to `Archive` — exactly option (b). See §2.

3. **"ask the agent to produce some exact feedback that clearly indicates
    that it was its intention not to reply."** YES. A `{{NO_REPLY}}`
   sentinel is defined. `agents/assistant.md` Phase 4 (Reply) gets a new
   step 0 instructing the agent to output exactly this sentinel when it
   chooses not to reply. See §2.

4. **"Simply an empty reply 'could' also result from a problem."** YES.
   The loop treats an empty reply (no sentinel) as "a problem" and leaves
   the message UNSEEN for retry, per the owner's "in which case it can
   simply try again." See §2 and §3.

No deviations from the owner's proposals. The guard design, sentinel
choice, and error-handling branching implement the owner's instructions
as stated.

---

## 1. HTML Guardrail (Decision 1 — owner approved)

### 1.1 What the guard checks

The `md_to_html` tool (P2-008, confirmed in
`src/yoker_assistant/tools.py`) emits a constrained tag set only:
`<h1>`, `<h2>`, `<h3>`, `<p>`, `<strong>`, `<ul>`, `<li>`, `<table>`,
`<thead>`, `<tbody>`, `<tr>`, `<th>`, `<td>`, `<hr>`. ALL text content is
HTML-escaped via `html.escape(quote=False)` before wrapping. So on the
intended path, no `<script>`, `<img>`, `<style>`, `<iframe>`, event
handlers, or any tag outside that set can appear in the output.

The guard is a **denylist of substrings and one attribute regex** that
indicate the agent bypassed `md_to_html` (the prompt-injection residual
identified in `security-loop.md` M1). The patterns map directly to the
documented risks: tracking pixels (`<img`), script (`<script`), CSS-based
spoofing (`<style`), embedded content (`<iframe`, `<object`, `<embed>`),
form-based phishing (`<form`), and inline event handlers (`on\w+=`).

```python
import re

_UNSAFE_HTML_TAGS = (
  "<script", "<style", "<img", "<iframe",
  "<object", "<embed", "<form",
)
_UNSAFE_ATTR_RE = re.compile(r"\bon\w+\s*=", re.IGNORECASE)


def _contains_unsafe_html(html: str) -> bool:
  """Return True if html contains tags/attributes md_to_html never emits.

  md_to_html escapes all text and emits only h1-h3, p, strong, ul, li,
  table/thead/tbody/tr/th/td, hr. Any other tag or any on*= event handler
  indicates the agent bypassed md_to_html (e.g. via prompt injection).
  """
  lowered = html.lower()
  return any(p in lowered for p in _UNSAFE_HTML_TAGS) or bool(
    _UNSAFE_ATTR_RE.search(html)
  )
```

7 lines of logic. No new dependency. No HTML parser. No allowlist
machinery. This is the simple approach the owner asked for.

**Why not an allowlist?** An allowlist (parse the HTML, reject unknown
tags) would be more robust but requires an HTML parser dependency
(`beautifulsoup4` or `lxml`) and ~30-40 lines of code. The owner's
simplicity directive and the security-engineer's own recommendation
("~5 lines, check for `<script`/`<img`/`<style`") point to a denylist.
The denylist covers the documented risks (tracking pixels, script, CSS
spoofing, iframes, event handlers). This is defense-in-depth on top of
`md_to_html`'s escaping, not the primary safety boundary (which is the
recipient whitelist, C1).

**Why not include `<a`?** `md_to_html` does not emit `<a>` tags (it has
no link syntax). A `<a>` tag in the output would also indicate bypass.
However, links are borderline (phishing risk, but the owner might
legitimately want the agent to include links in future). The guard
focuses on the unambiguously harmful set. `<a` can be added later if the
owner wants stricter checking.

### 1.2 Where the guard lives

In `loop.py`, as a module-level function `_contains_unsafe_html(html)`.
Not in `tools.py` (it is loop-side defense, not part of the
`md_to_html` tool's contract). Not in a new module.

### 1.3 What happens when the guard triggers

The guard firing means the agent produced HTML that `md_to_html` would
never emit — i.e. a prompt-injection bypass. This is "a problem" per the
owner's decision-2 framing, but it is NOT a transient problem (network
blip, LLM hiccup) — retrying the same adversarial message will produce
the same unsafe output with high probability and loop forever.

**Recommended action on guard failure:**
1. Do NOT send the reply.
2. Log a warning with the message id.
3. Mark the message `\Seen` (stops UNSEEN retry → no infinite loop).
4. Do NOT archive (leaves it visible in INBOX for the owner to debug).

This is the simplest approach that (a) prevents the unsafe reply from
reaching the owner, (b) avoids an infinite retry loop, and (c) keeps the
problem visible rather than burying it in Archive. It deviates from the
owner's "try again" framing for empty/exception cases because guard
failures are non-transient — retrying adversarial input is futile. The
deviation is justified: the owner's "try again" applies to problems that
might resolve on retry (empty reply, exception); guard failures on
prompt-injected input will not.

**Alternative the owner may prefer:** if the owner wants strict "try
again" semantics for ALL problem cases, the guard-failure path can leave
the message UNSEEN instead. Risk: infinite retry on a persistent
prompt-injection payload. Not recommended unless the owner accepts that
risk or adds a retry-count cap (out of scope for the first pass).

---

## 2. Explicit No-Reply Sentinel (Decision 2 — owner's new requirement)

### 2.1 The sentinel

```python
NO_REPLY_SENTINEL = "{{NO_REPLY}}"
```

**Why `{{NO_REPLY}}`:**
- Double curly braces are extremely unusual in natural English text and
  in markdown — they do not appear in normal prose, markdown syntax,
  code blocks that a personal assistant would typically write, or the
  `md_to_html` tool's output vocabulary.
- It is a single literal string (simple, per the owner's directive).
- It will not collide with the HTML guard (`{{` is not `<`).
- It is visually distinct and self-documenting.
- It survives the `md_to_html` pipeline unchanged: if the agent outputs
  `{{NO_REPLY}}` as markdown, `md_to_html` wraps it in
  `<p>{{NO_REPLY}}</p>`; the loop detects the sentinel via a substring
  check in both the raw and wrapped cases.

**Why not `<no-reply/>`:** an XML-like tag could be confused with the
HTML the agent emits, and it adds ambiguity about whether `md_to_html`
should pass it through.

**Why not `[NO_REPLY]`:** single brackets appear frequently in markdown
(link syntax, citations) and natural text; higher collision risk.

**Detection:** `NO_REPLY_SENTINEL in reply_html` (substring check).
This handles both the raw sentinel and the `<p>{{NO_REPLY}}</p>`
md_to_html-wrapped form. False-positive risk (the agent includes
`{{NO_REPLY}}` inside a real reply discussing the sentinel mechanism) is
negligible and acceptable for a personal assistant replying to its
owner.

### 2.2 Agent definition update (`agents/assistant.md`)

The instruction goes in **Phase 4: Reply**, as a new step 0 before the
existing step 1. This is where the reply decision is made — the right
place. No new section, no restructure.

Exact wording to insert (5 lines, after the `Phase 4: Reply` fence open,
before the existing `1. Compose the reply...`):

```
0. If you choose NOT to reply to this email (e.g. it is spam, a
   duplicate, or requires no action and no clarification), output
   exactly `{{NO_REPLY}}` as your reply body and nothing else. This
   explicitly signals the loop that your non-reply is intentional,
   distinguishing it from an error that produced an empty reply. Do
   NOT output an empty string to indicate "no reply" — always use the
   sentinel. The sentinel goes through `md_to_html` like any reply;
   the loop detects it and archives the message without sending.
```

This is a 5-line addition to a 317-line file. The existing steps 1-4
are renumbered 1-4 → 1-4 (step 0 is prepended; no renumbering needed
since step 0 is new). Actually, the existing steps are numbered 1-4;
adding step 0 before them requires no renumbering of the existing
steps.

### 2.3 Loop interpretation — four-way branching in `_process_one`

The existing `_process_one` (from `api-loop.md`) has two branches:
non-empty reply → send+mark+archive; empty reply → mark+archive. The
revision replaces this with **four explicit branches**:

```python
NO_REPLY_SENTINEL = "{{NO_REPLY}}"

async def _process_one(imap, smtp, agent, mid: str) -> None:
  msg = await imap.fetch_message(mid, folder=_INBOX_FOLDER)
  message = build_message(msg)
  reply_html = await agent.process(message)

  # Branch 1: intentional no-reply (sentinel present)
  if NO_REPLY_SENTINEL in reply_html:
    logger.info("agent signalled no-reply; marking read and archiving",
                message_id=mid)
    await imap.mark_message(mid, _INBOX_FOLDER, "\\Seen", "add")
    await imap.move_message(mid, _INBOX_FOLDER, _ARCHIVE_FOLDER)
    return

  # Branch 2: empty reply = "a problem" → leave UNSEEN for retry
  if not reply_html.strip():
    logger.warning(
      "agent returned empty reply (no sentinel); leaving UNSEEN for retry",
      message_id=mid)
    return

  # Branch 3: HTML guard failed → don't send, mark read, don't archive
  if _contains_unsafe_html(reply_html):
    logger.warning(
      "HTML guard rejected reply; marking read without archiving",
      message_id=mid)
    await imap.mark_message(mid, _INBOX_FOLDER, "\\Seen", "add")
    return

  # Branch 4: normal reply → send → mark read → archive (§4.4 ordering)
  sender = parseaddr(msg.get("from", ""))[1]
  subject = msg.get("subject", "")
  await smtp.reply_email(
    to=sender,
    subject=f"Re: {subject}",
    body="",  # plain-text alternative intentionally empty (§4.3)
    html_body=reply_html,
    in_reply_to=msg.get("message_id", ""),
  )
  await imap.mark_message(mid, _INBOX_FOLDER, "\\Seen", "add")
  await imap.move_message(mid, _INBOX_FOLDER, _ARCHIVE_FOLDER)
```

**Note on the outer try/except:** the existing `run()` wraps each
`_process_one` call in `try/except Exception` that logs and leaves the
message UNSEEN (§7 "unexpected exception" handling). That outer handler
covers `agent.process()` raising, `fetch_message` raising, and any
IMAP/SMTP exception. The four branches above handle the non-exception
outcomes. No new try/except inside `_process_one` is needed — exceptions
bubble to the outer handler, which already does the right thing (leave
UNSEEN, retry next iteration). This preserves §7's existing error
handling.

### 2.4 Branch-by-branch summary

| Agent output | Loop action | Message state after | Rationale |
|---|---|---|---|
| Contains `{{NO_REPLY}}` | Mark read + archive | Read, in Archive | Intentional no-reply (owner decision 2, option b) |
| Empty / whitespace only | Nothing (leave UNSEEN) | Unread, in INBOX | "A problem" → retry next iteration (owner decision 2) |
| Non-empty, fails HTML guard | Mark read, do NOT archive | Read, in INBOX | "A problem" but non-transient; mark read stops infinite retry, keep visible for debug |
| Non-empty, passes guard | Send + mark read + archive | Read, in Archive | Normal reply (§4.3/§4.4) |
| `agent.process()` raises | Outer handler: log, leave UNSEEN | Unread, in INBOX | "A problem" → retry (§7, unchanged) |

---

## 3. Error-handling change (§7 of functional.md)

§7 currently says:
- Agent `process` failure: log, do not mark read, continue. Retries next iteration.
- Reply send failure: do not mark read; retry next iteration.
- Unexpected exception per message: log, skip (leave UNSEEN), continue.

The revision extends §7 with two new explicit cases (and leaves the
existing three unchanged):

- **Empty reply (no sentinel):** "a problem" → log warning, leave UNSEEN,
  retry next iteration. (Owner decision 2: "in which case it can simply
  try again.")
- **HTML guard failure:** "a problem" but non-transient → log warning,
  mark read (stop retry), do NOT archive (keep visible). Do NOT send.
- **Sentinel `{{NO_REPLY}}`:** intentional no-reply → mark read + archive.
  Not an error.

The existing §7 cases (process exception, send failure, unexpected
exception) are unchanged — they all leave UNSEEN and retry.

---

## 4. Scope impact

### 4.1 Files touched

| File | Change | Lines added (approx) |
|---|---|---|
| `src/yoker_assistant/loop.py` | Add `_UNSAFE_HTML_TAGS`, `_UNSAFE_ATTR_RE`, `_contains_unsafe_html()`, `NO_REPLY_SENTINEL` constant; rewrite `_process_one` with four-way branching | ~25 net (replaces the existing two-branch `_process_one`) |
| `agents/assistant.md` | Insert step 0 in Phase 4: Reply | ~5 |
| `tests/test_loop.py` (P3-002, not yet implemented) | Add tests for sentinel, guard, four-way branching | ~35 (within the P3-002 test suite) |
| `analysis/functional.md` | Update §4.3, §7, and §4.4 to reflect the sentinel and guard (docs errata) | ~15 |

**No module structure change.** No new files. No new dependencies. The
guard and sentinel detection are functions/constants in `loop.py`.

### 4.2 Test plan changes (P3-002)

P3-002's test suite must add the following behavior-based tests (all
with fake IMAP/SMTP/Agent stubs, no network, no real backend):

1. **Sentinel → no-reply path:** agent stub returns `"{{NO_REPLY}}"` →
   loop calls `mark_message` + `move_message`, does NOT call
   `reply_email`.
2. **Sentinel (HTML-wrapped) → no-reply path:** agent stub returns
   `"<p>{{NO_REPLY}}</p>"` → same behavior as test 1.
3. **Empty reply → retry path:** agent stub returns `""` → loop does
   NOT call `reply_email`, `mark_message`, or `move_message` (leaves
   UNSEEN).
4. **HTML guard — `<script>`:** agent stub returns
   `"<p>ok</p><script>alert(1)</script>"` → loop does NOT call
   `reply_email`, calls `mark_message` (read), does NOT call
   `move_message`.
5. **HTML guard — `<img>`:** agent stub returns
   `'<p>hi</p><img src="https://attacker/track.png">'` → same as test 4.
6. **HTML guard — event handler:** agent stub returns
   `'<p onload="alert(1)">hi</p>'` → same as test 4.
7. **Safe HTML → normal path:** agent stub returns `"<p>hello</p>"` →
   loop calls `reply_email(html_body="<p>hello</p>", ...)`, then
   `mark_message`, then `move_message` (existing P3-002 test, retained).

Tests 1-6 are new; test 7 is the existing P3-002 behavior. The
`html_body=` routing assertion (absorbed from the descoped P3-003) is
retained in test 7.

### 4.3 What does NOT change

- Module structure (`loop.py` + `__main__.py`, no `handoff.py`).
- `build_message` design (pure function, no I/O, no instructions block).
- The SDK errata from `api-loop.md` (SMTP no connect, `to: str`, `body=""`
  required, `move_message` source folder, `parseaddr` for sender).
- C1 blocking fix (startup whitelist check).
- The `--once` flag, graceful shutdown, poll interval.
- The Wrapper Check (still PASS — the guard and sentinel are functions
  and constants, not wrapper classes).

---

## 5. Simplicity principle check

The owner's simplicity directive is respected:

- **Sentinel:** one literal string `{{NO_REPLY}}`. One `in` check. No
  regex, no parser, no structured-output protocol.
- **Guard:** one function, ~7 lines, no dependency, no HTML parser. A
  denylist of 7 tag prefixes + one attribute regex.
- **Agent.md update:** 5 lines inserted into an existing section. No new
  section, no restructure, no rewrite.
- **Loop branching:** four explicit branches, flat (no nesting), each
  returning early. Clearer than the existing two-branch version.
- **Error handling:** the §7 extension adds two lines of documentation;
  the actual code paths are the four branches above.
- **No new modules, no new dependencies, no new abstractions.**

---

## 6. Concerns

1. **Sentinel false-positive risk:** if the agent ever includes
   `{{NO_REPLY}}` in a real reply (e.g. discussing the sentinel
   mechanism with the owner), the loop would treat it as no-reply and
   archive the message without sending. Negligible for a personal
   assistant replying to its owner; acceptable.

2. **Denylist vs allowlist:** the HTML guard is a denylist. A
   sophisticated attack could craft HTML using tags not in the denylist
   (e.g. `<svg onload=...>` — but `onload=` IS caught by the regex; or
   `<a href=javascript:...>` — not caught, see §1.1 note on `<a>`). The
   denylist covers the documented risks (tracking pixels, script, CSS,
   iframes, event handlers). An allowlist would be more robust but
   requires a parser dependency and ~4x the code. The owner approved the
   guard approach; the denylist is the simple implementation. The
   primary safety boundary remains the recipient whitelist (C1).

3. **Guard failure is non-transient:** marking read on guard failure
   means the message will not retry. If the guard fires on a false
   positive (unlikely with the current patterns), the message is marked
   read but not archived — the owner can still see it in INBOX and
   re-forward it. Acceptable for a demo.

4. **Sentinel goes through `md_to_html`:** if the agent follows Phase 4,
   it calls `md_to_html` on `{{NO_REPLY}}` and gets
   `<p>{{NO_REPLY}}</p>`. The substring check catches this. If the agent
   does NOT call `md_to_html` and outputs `{{NO_REPLY}}` raw, the
   substring check still catches this. Both paths work.

5. **No change to the `pa-inbox`/`pa-outbox` skill evaluation tasks
   (P2-002/P2-003):** the sentinel instruction lives in the agent
   definition, not in a skill. If those later evaluations split reply
   logic into a skill, the sentinel instruction moves with it. Not a
   blocker for this task.

---

## 7. Summary of changes to the implementation plan

The existing implementation plan (from `api-loop.md`) is amended as
follows:

1. **`loop.py` gains `_contains_unsafe_html()` and `NO_REPLY_SENTINEL`.**
   Two module-level additions.

2. **`_process_one` is rewritten with four-way branching** (sentinel /
   empty / guard-fail / normal) replacing the existing two-way
   (non-empty / empty) branching. The outer `try/except` in `run()` is
   unchanged.

3. **`agents/assistant.md` Phase 4 gains step 0** (5 lines) instructing
   the agent to emit `{{NO_REPLY}}` when it chooses not to reply.

4. **`analysis/functional.md` §4.3 and §7 are updated** to document the
   sentinel, the guard, and the four-way branching. §4.4 ordering is
   unchanged.

5. **P3-002 test plan gains 6 new test cases** (sentinel detection,
   HTML-wrapped sentinel, empty reply, three guard-failure variants).

6. **All other plan items from `api-loop.md` are unchanged** (module
   structure, `build_message`, `run()`, `__main__.py`, SDK errata, C1
   fix, Wrapper Check).

This revision is ready to be posted as a PR comment on PR #7 for owner
approval. No implementation is started until the owner confirms.