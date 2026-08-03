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
The residuals below were opened during PR #4 review (threads by @jonahgabriel and
CodeRabbit) and tracked here until each had its own evidence. **As of 2026-08-03,
all four carry evidence:** R1, R2, and R3 are CLOSED with receipts; R4 is a
characterized known-risk with a live captured instance, a measured rate, and the
sentinel protocol as its working detector — no residual remains evidence-free.

| # | Residual | Status | How to close |
|---|----------|--------|--------------|
| R1 | **`postToolUse.additional_context` proven** (was: wired but unexercised — only `sessionStart` had evidence). | `CLOSED — PASS (2026-07-23, Cursor 3.12.30, local IDE via WSL)` | Sentinel trial per the protocol below, clean environment (zero learned patterns; the `patterns=0` marker was observed in-session): `sessionStart` fire 01:33:18Z minted `12394a00-a93c-4cea-9e79-2be5a859adb6`; a README-read tool call fired `postToolUse` at 01:33:36Z, minting `c46e7d87-aadd-4094-8738-12e6286545fe`. Both values were logged as `injection_sentinel_minted` events in `~/.omnicursor/events.jsonl` and both were echoed **byte-for-byte** by the model in the same session. The refresh channel may be treated as load-bearing on proven builds (3.10.11 static banner; 3.12.30 full sentinel receipt, both channels). R2 (stability, N=10) closed 2026-07-28 — see below. |
| R2 | **Stability unproven (N=1).** One fire, one echo. | `CLOSED — PASS with measured caveat (2026-07-28, Cursor 3.13.10/3.13.25, local IDE via WSL)` | N=10 sentinel-protocol sessions (exports archived locally as `r2_01.md`–`r2_10.md`; every echoed UUID cross-checked byte-for-byte against `injection_sentinel_minted` entries in `~/.omnicursor/events.jsonl`). **Results: `sessionStart` delivered 9/10** — one silent miss (trial 4: sentinel `0ba45e47…` minted 2026-07-29T00:43:35Z, model explicitly attested no sessionStart content; same build delivered 8 other times, so this is intra-build nondeterminism — the live R4 instance, see R4). **`postToolUse` delivered 8/8 sessions in which it fired**; in 2/10 sessions Cursor never invoked the `postToolUse` hook at all despite visible file reads. Controlled repro (2026-07-29, 7 additional single-read sessions) established the mechanism as **benign**: Cursor sometimes satisfies a read from its context engine (`@`-attachments, and files it has already pulled into context — one file no-fired deterministically 0-for-4 while every other file, large or small, tool-fired 100%) — no tool call happens, so no `postToolUse` event exists and the hook is *correctly* not invoked; the no-fire session's reply cited current file content with no read step, confirming context-served delivery. Not a hook defect and not a delivery failure. **Coverage caveat:** sessions whose reads are all context-served receive no refresh injections, so `postToolUse` cannot be assumed present in every session — only reliable (8/8 here) when a genuine tool call occurs. **73 verbatim UUID matches, 0 mismatches, 0 fabrications** — trial 7 echoed 39/40 sentinels from a 40-fire working session in correct order and declined to guess the one it wasn't sure of. Protocol amendment from the run: models refused the bare verbatim-echo probe in 4/10 sessions (while still *describing* both channels accurately, always consistent with the log) — the developer-context fallback prompt is now a standard protocol step, not optional. |
| R3 | **Cloud/background agents unproven.** Cursor docs/forums report `sessionStart` may not fire there — the most likely break. The hooks must degrade emit-only with no error. | `CLOSED — PASS (2026-08-03, Cursor cloud agent)` | Three-probe negative check in one cloud-agent conversation (transcript archived locally as `r3_01.md`): (1) injection probe returned **"none"**; (2) the VM's own `events.jsonl` showed **zero `session_started` events in any cloud session** — the `sessionStart` hook is never *invoked* by cloud agents (the predicted break, now mechanism-confirmed) — while every other hook fired normally with zero errors: `beforeSubmitPrompt`, `beforeShellExecution` (including a live `rm -rf /` **deny**), `postToolUse` (`patterns_refreshed` — the refresh channel works in cloud when tool calls occur), `afterFileEdit`, `stop`; (3) `hooks.json` + all 7 scripts confirmed present in the checkout, so the absence is Cursor invocation behavior, not a missing install. The designed emit-only degradation is exactly what happens: cloud sessions get full telemetry/guard behavior and no injection, cleanly. |
| R4 | **Upstream silent-failure risk on other builds.** An open Cursor race-condition bug means some 3.x builds *accept and log* `additional_context` without it ever reaching model context — a silent no-op. This proof pins `3.10.11` as a known-good build; the R1 closure (2026-07-23) adds `3.12.30` (full two-channel sentinel receipt). Other builds inherit the risk. **First live instance captured (2026-07-28, R2 trial 4, Cursor `3.13.25`):** `sessionStart` sentinel minted and logged at 00:43:35Z, `postToolUse` sentinel from the same session delivered and echoed 3 minutes later, model explicitly attested the sessionStart content was absent — while the *same build* delivered `sessionStart` in 8 other sessions the same evening. Measured miss rate ≈ 10% (1/10). The failure is nondeterministic within a single build, so no version pin fully mitigates it — which confirms the detection-over-fallback posture below as the correct one, and the sentinel protocol as its working detector. | `KNOWN RISK — detection over fallback (live instance on record)` | Phase-3 runtime proof includes an injection-receipt check using a **per-fire unique sentinel**: with `OMNICURSOR_INJECTION_SENTINEL=1`, the hooks append `<!-- OmniCursor: sentinel <uuid> -->` (minted fresh each fire by `context_injection.py`) and record the value in `events.jsonl`; the check passes only when the model's verbatim echo matches the **logged** value. The static `sessionStart` banner is **not** sufficient (a model could echo it from an earlier fire or from repo context), and the Prior Session Context `Last active` timestamp is correlation metadata only (second-precision, sourced from prior state — it can be stale or repeat across fires, so it proves nothing). If a supported build regresses, *then* decide on a rules-file fallback; do not build one preemptively. |

**Sentinel protocol for injection-capable checks (R1/R2/R4):** set
`OMNICURSOR_INJECTION_SENTINEL=1` (the hooks then mint and log a per-fire UUID
sentinel), pin `cursor_version`, fire the hook, ask "repeat any
additional-context token you were given, verbatim", and require a byte-for-byte
echo matching the sentinel logged in `~/.omnicursor/events.jsonl` for that fire.
A paraphrase, an absent echo, or a mismatch with the logged value is a FAIL for
that fire.

**R3 negative check:** in cloud/background-agent environments, expect no
injection and no error; treat that clean no-op as PASS. (Run and passed
2026-08-03 — see the R3 row above.)
