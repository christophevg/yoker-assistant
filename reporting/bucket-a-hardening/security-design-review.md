# Security Design Review — S-01 SECURITY.md (Phase 3, pre-implementation)

**Reviewer:** security-engineer
**Date:** 2026-07-23
**Scope:** S-01 only — the proposed `SECURITY.md` content in `reporting/bucket-a-hardening/plan.md` (lines 297-368) and the README.md subsection (lines 373-385).
**Reference code:** `src/yoker_assistant/__init__.py` (manifest declares one tool: `md_to_html`), `src/yoker_assistant/tools.py` (bounded pure-function str→str converter, XSS fix already applied per `analysis/security-md-to-html-tool.md`).

## Verdict: APPROVE with changes

The proposed content is tight, correctly scoped, and matches the actual threat model (once-at-install-time trust, no per-call gate). No restructuring needed. Three targeted adjustments below sharpen the framing and close two real gaps. No sections need to be added wholesale — in particular, do **not** add a supported-versions table or a CVE-handling section (see (c)).

## (a) Three-pillar structure — correct, do not restructure

The blast-radius / capability / version-pinning frame is the right organization for this project. A threat-model-first (STRIDE-per-tool) structure would be heavier than the single-tool manifest warrants and would duplicate what the three pillars already encode:

- **Blast-radius** (inputs/outputs/reach/failure modes) is a lightweight data-flow / failure analysis — the STRIDE "Information Disclosure" + "Denial of Service" axes in pragmatic form.
- **Capability review** (duplicates / composition / bounded-args) is the STRIDE "Elevation of Privilege" + "Tampering" axis — and the composition check (`yoker:git` / `yoker:write` / `yoker:webfetch`) is the single most valuable item in the doc, because it catches exfiltration and persistence paths that a per-tool review would miss.
- **Version pinning** is the supply-chain axis (OWASP A03 / A08) — the right place for it.

Threat-model-first would add a STRIDE matrix per tool, which for a 0.1.0 package with one bounded tool is ceremony without payoff. Keep the three pillars.

## (b) Framing — close, needs sharpening (not a hard block)

The line (plan.md line 358-359):

> A manifest addition merged without this checklist is a process bug, not
> a security incident — but it will be reverted.

is the right **stance** (not a hard CI block — CI cannot meaningfully check a judgment-call review; a hard block would just be bypassed) but the framing is too soft in one direction and too binary in another:

- Too soft: "process bug" risks normalizing the slip. Once-at-install-time trust means a tool that slipped in has already run with no per-call gate for every user who updated before the revert. That is a live exposure window, not just a paperwork miss.
- Too binary: "it will be reverted" stops short of what the revert must trigger.

**Adjustment — replace those two lines with:**

> A manifest addition or capability-changing edit merged without this
> checklist is a process violation: it is not automatically a security
> incident, but it triggers (1) immediate revert of the change, and (2) a
> retroactive security review of what the unreviewed code did while live,
> covering the exposure window from merge to revert. CI does not enforce
> this — it is a reviewer judgment gate.

This keeps the "not a hard block" property (so CI isn't pretending to check it) and the "not automatically an incident" property (so the disclosure process isn't triggered by every checklist miss), but makes the exposure-window review explicit and names what the revert must kick off.

## (c) Missing sections — two small gaps, two deliberate non-additions

### Gap 1 (blocking adjustment) — scope is too narrow: "additions" only

The doc covers **additions** to `__YOKER_MANIFEST__` but not **capability-changing edits to existing tools**. A change to `md_to_html` that, say, adds a `file_path` argument and reads from disk is exactly as security-relevant as a new tool, and it bypasses the "addition" framing. The blast-radius / capability / pinning pillars apply identically.

**Adjustment — in the opening of the `__YOKER_MANIFEST__` Addition Review Process section (plan.md line 306-317), widen the scope.** Replace:

> Contributors MUST follow this review process before merging a manifest
> addition.

with:

> Contributors MUST follow this review process before merging a manifest
> addition **or a capability-changing edit to an existing tool** (new
> args, new side effects, new dependencies, or a change to the tool's
> reach). Pure refactors that do not change the tool's inputs, outputs,
> reach, or failure modes do not require this review.

And rename the section heading from `## __YOKER_MANIFEST__ Addition Review Process` to `## __YOKER_MANIFEST__ Change Review Process`.

The PR checklist (plan.md line 349-356) already says "manifest addition" — update the first checklist item to "Blast-radius assessment recorded (for an addition or a capability-changing edit)".

### Gap 2 (minor adjustment) — coordinated disclosure response window

The "Reporting a Vulnerability" section (plan.md line 302-304) is placeholder text:

> <standard text: email christophe.vg, no public disclosure until fix released>

This is fine as a placeholder for implementation, but the implementation must state an expected response window so reporters know what to expect. One line is enough:

> Email christophe.vg with a description and repro. Expect an
> acknowledgement within 72 hours and a fix or mitigation plan within
> 30 days for the current release line. Do not publish until the fix is
> released unless we agree otherwise.

Do **not** add a PGP key, a security.txt, or a formal CVE-handling process — for a 0.1.0 single-tool plugin provider those are ceremony (Simplicity Principle). The owner can request a CVE from GitHub's security advisory workflow if a real vuln ever lands; that's a one-line footnote at most, not a section.

### Deliberate non-addition 1 — no supported-versions table

A supported-versions matrix is premature for a 0.1.0 package with one tool and no released security history. It would be a maintenance burden and would go stale immediately. Skip it. If/when there are multiple release lines or a real CVE lands, add it then.

### Deliberate non-addition 2 — no CVE-handling section

CVE handling for a plugin provider of this size is "use GitHub Security Advisories if it ever happens". Documenting a formal CVE process now is speculative policy-writing. Skip it.

## Simplicity Principle check — no over-engineering found

The proposed doc is ~70 lines of markdown. The three pillars are each 4-6 bullets. The PR checklist is 6 items. No wrappers, no indirection, no "Security Council" or "Review Board" invented. The Publishing Guards section (plan.md line 361-367) is the only borderline item — it's arguably CONTRIBUTING.md material rather than SECURITY.md material — but since S-02 is a security control and a SECURITY.md reader benefits from knowing it exists, keeping it as a short pointer is fine. Do not expand it beyond the current 7 lines.

The README.md subsection (plan.md line 373-385) is correctly tight and links out to SECURITY.md rather than duplicating it. No changes needed there.

## Specific content adjustments (quoted)

1. **plan.md line 358-359** — replace the "process bug... will be reverted" two lines with the text in §(b) above (immediate revert + retroactive exposure-window review; not CI-enforced).
2. **plan.md line 306-317** — widen scope from "manifest addition" to "manifest addition or capability-changing edit to an existing tool", with the pure-refactor carve-out. Rename the section heading to `__YOKER_MANIFEST__ Change Review Process`.
3. **plan.md line 349-356 (checklist item 1)** — update to "Blast-radius assessment recorded (for an addition or a capability-changing edit)".
4. **plan.md line 302-304** — replace the placeholder with the 72-hour-ack / 30-day-fix line in §(c) Gap 2.

## Scope classification

| Finding | Classification | Action |
|---|---|---|
| (b) Revert framing too soft — exposure-window review not triggered | Blocking | Apply adjustment 1 in S-01 |
| (c) Gap 1 — scope narrow (additions only, misses capability-changing edits) | Blocking | Apply adjustments 2 + 3 in S-01 |
| (c) Gap 2 — no disclosure response window | Related | Apply adjustment 4 in S-01 |
| Supported-versions table | New (deferred) | Do not add now; revisit if multi-line or first CVE |
| CVE-handling section | New (deferred) | Do not add now; use GitHub Security Advisitories if needed |

## Positive observations

- The composition check against `yoker:git` / `yoker:write` / `yoker:webfetch` is the right cross-tool exfil/persistence gate — this is the doc's strongest section.
- "Unbounded tools are rejected by default" (plan.md line 337-338) is a clear, correct default that matches the bounded-args discipline already enforced in `tools.py` (`Annotated[str, Text(...)]`, no `**kwargs`).
- Version-pinning pillar correctly ties to `pyproject.toml` + `uv pip install ==<version>` rather than inventing a new mechanism.
- README subsection correctly defers detail to SECURITY.md and names the whitelist env var as the reply-safety boundary — keeps the two concerns (tool-trust vs reply-safety) distinct.
- The doc does not pretend CI enforces the review — important honesty given the judgment-call nature.