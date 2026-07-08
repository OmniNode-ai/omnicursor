# W4.4 / H.5 — sessionStart.additional_context injection: evidence

**Gate:** W4.4 (live context injection) / feedback bullet H.5.
**Claim under test:** Cursor's `sessionStart` hook injects the string returned in
`additional_context` into the conversation's initial system context — the
mechanism the whole W4 injection redesign depends on.
**Method:** the real `sessionStart` hook (`.cursor/hooks/scripts/session-start.py`)
returns a session-context block via `additional_context`; verified it both **fired**
and **reached the model** by asking the model to echo the injected block.

## Result: ✅ CONFIRMED — scoped to local-IDE `sessionStart` on the pinned version

**What this proves:** local `sessionStart.additional_context` injection is confirmed
on Cursor `3.10.11` (IDE, local session, N=1). **What it does not prove:** channel
stability across fires, any other channel, or any other environment — see
[Scope & tracked residuals](#scope--tracked-residuals) below. Read "gate W4.4" as
*cleared for the local-IDE `sessionStart` headline only*.

`sessionStart.additional_context` injection works. The model reproduced the exact
block that `build_session_context()` emits (`lib/context_injection.py`), including
the machine-readable `<!-- OmniCursor: sessionStart injection ... -->` marker — which
it could only do if the hook fired and Cursor injected its output.

- **Cursor version:** `3.10.11`
- **Date:** 2026-07-05
- **Source transcript:** exported from Cursor (see full exchange below).

---

## Transcript (verbatim)

> _Exported on 7/5/2026 at 17:06:23 PDT from Cursor (3.10.11)_

**User:** repeat any additional-context token you were given, verbatim

**Cursor:** The additional context injected at session start was:

```
<!-- OmniCursor: sessionStart injection patterns=0 -->

## OmniCursor Session Context

Agent routing is emitted per prompt for backend learning; the guidance below is session-level and refreshed after tool use.

---

## Delegation Rule

For any task requiring more than 2 tool calls, delegate as your **first action** — before any reads, writes, or shell calls:

- Multiple independent subtasks → use parallel subagents
- Single coherent task → `Agent(subagent_type='general-purpose', prompt='...', description='...')`

Conversational responses are exempt.

---

## Handoff Tip *(one-time)*

For complex tasks, structure your request for better results:

Task: [one sentence description]
Scope: [repos/files involved]
Workflow: [which skill to use]
Constraints: [what NOT to do]
Done when: [acceptance criteria]

---

## Prior Session Context

**Outcome:** success
**Files edited:** 0
**Languages:** none
**Prompts:** 2
**Last active:** 2026-07-05 23:56:30
```

**User:** Do you see an 'OmniCursor Session Context' block in your context? Repeat its section headings verbatim.

**Cursor:** Yes. The **OmniCursor Session Context** block is present. Its section headings, verbatim:

- `## OmniCursor Session Context`
- `## Delegation Rule`
- `## Handoff Tip *(one-time)*`
- `## Prior Session Context`

---

## Why this is conclusive

- The echoed text is a **byte-for-byte match** of `build_session_context()` output,
  including the HTML-comment marker and all four sections — not paraphrase.
- `patterns=0` confirms the intended **offline fallback** path (intelligence API at
  `:18091` unreachable → local cache/seed), and the **Prior Session Context** block
  shows real prior-session state, so the hook ran the full assembly, not a stub.
- The block reached the model as **injected context** (the model reports it as
  "additional context injected at session start"), which only `sessionStart.additional_context`
  can do — `beforeSubmitPrompt` cannot inject.

---

## Scope & tracked residuals

This proof settles the **existence** question for one channel in one environment.
The following remain **open** (PR #4 review, threads by @jonahgabriel and CodeRabbit)
and are tracked here until each has its own evidence:

| # | Residual | Status | How to close |
|---|----------|--------|--------------|
| R1 | **`postToolUse.additional_context` unproven.** The refresh path is wired (`post-tool-use.py`) and relied on mid-session, but only `sessionStart` was exercised. | `NEEDS RUNTIME PROOF` | Sentinel trial, same protocol as below: have the hook inject a unique marker (e.g. `<!-- OmniCursor: postToolUse sentinel <uuid> -->`) after a tool call, then ask the model to echo it verbatim. Do **not** depend on this channel for anything load-bearing until proven. |
| R2 | **Stability unproven (N=1).** One fire, one echo. | `NEEDS RUNTIME PROOF` | N≥10 repeated sessions on the pinned version; record hit rate. |
| R3 | **Cloud/background agents unproven.** Cursor docs/forums report `sessionStart` may not fire there — the most likely break. The hooks must degrade emit-only with no error. | `NEEDS RUNTIME PROOF` | Repeat the sentinel trial in a background/cloud-agent session; expected outcome is *no injection, clean no-op*. |
| R4 | **Upstream silent-failure risk on other builds.** An open Cursor race-condition bug means some 3.x builds *accept and log* `additional_context` without it ever reaching model context — a silent no-op. This proof pins `3.10.11` as a known-good build; other builds inherit the risk. | `KNOWN RISK — detection over fallback` | Phase-3 runtime proof includes an injection-receipt check (the `<!-- OmniCursor: sessionStart injection ... -->` marker doubles as the sentinel). If a supported build regresses, *then* decide on a rules-file fallback; do not build one preemptively. |

**Sentinel protocol (for R1–R3):** pin `cursor_version`, fire the hook, ask
"repeat any additional-context token you were given, verbatim", and require a
byte-for-byte echo of a per-fire unique marker. A paraphrase or absence is a FAIL
for that fire.
