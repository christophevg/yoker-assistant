# STANDARDS

## Purpose

This document is the shared quality bar for the yoker 1.0 pet-store showcase
packages. Both `yoker-assistant` and its sister project
`yoker-writing-assistant` inherit these standards. Each project carries its own
copy; the two copies are kept in sync. Anything not governed here is left to
each project's own judgment.

## Doc voice

Docs are written as "how was this built?" tutorials. A reader follows the
journey from an empty repo to a working package and understands why each
decision was made along the way. We do not write reference docs. We do not write
spec dumps. The build narrative is a deliverable, not an afterthought: if a
choice was made, the docs explain it.

## Ultra clean

Small surface area. Clear module boundaries. No dead code. No speculative
abstractions. Every line earns its place. If a reader asks "why does this
exist?" the answer should be obvious from the code and the docs together.
When in doubt, cut it.

## Tight code: right tool for the right job

Each side does exactly its job and nothing more. In `yoker-assistant`, Python
owns the cheap structured loop: poll the mailbox, parse the message, hand off
to the agent, send the reply. The agent owns the reasoning. No agent cost is
spent on structured work. No Python is spent on reasoning. The principle is
plain: the right tool does the right job, and the two halves do not bleed into
each other.

## Limited but useful tests

Tests are behavior-based, not implementation-based. They cover what matters:
the handoff contract between Python and the agent, the polling logic, and the
mailbox integration seam. They are not exhaustive. They are not minimal. The
word is "useful" — a test has to be one that would actually catch a real
regression, or it does not belong here.

## c3 to yoker adaptation

`c3` (`../c3`) is the heritage. Agent definitions and skills are adapted from
it. We keep the concepts — what an agent is, what a skill is — and rework the
mechanics for the yoker context. c3 runs inside Claude Code with its own
orchestrator; yoker is an SDK / runtime with different mechanics. The
adaptation is about the mechanics, not the ideas. Be explicit, in each adapted
piece, about what is kept verbatim and what is reworked.

## Showcase quality

These projects are reference material for yoker 1.0. People will read them to
learn how to build a yoker package. They set the bar. That is the weight they
carry, and it is why ultra clean and tight code are non-negotiable.

## The two modes

The pair demonstrates yoker's two modes. `yoker-assistant` is yoker-as-SDK:
Python owns the process and calls yoker as a library.
`yoker-writing-assistant` is yoker-as-runtime: yoker is the entry point and the
package runs under it. Each project's own docs explain its specific mode. This
shared bar governs both.