# OmniCursor Implementation Brief

This document is the working source of truth for implementing OmniCursor in this repository.
It reconciles three inputs that currently create confusion:

1. The OmniCursor architecture documents describe the target system.
2. `omnicursor-team-guidance.md` explains how to make the demo-critical pieces real.
3. `omniclaude-main/` is a read-only reference implementation that we may selectively adapt.

Use this document when prompting Cursor, Codex, or Claude to make architecture-aligned changes.

> **Current shape:** The “third layer” is the **`src/omnicursor/` Python library** (tests, CI, optional `python -c` debugging). IDE behavior is **rules + hooks + `skills/*.md` on disk**.

---

## 1. Decision Summary

The sponsor direction is **not** to replace the architecture document with the guidance doc.
It says:

- the **architecture direction is correct**
- the **rules + hooks + library** model is correct
- the guidance doc contains the **ready-to-use implementation patterns** that map directly to the demo

The practical reading is:

- Use the architecture doc for **what OmniCursor is**
- Use the guidance doc for **how to implement the next demo-critical steps**
- Use `omniclaude-main/` as a **read-only donor/reference**, not as something to mirror wholesale

---

## 2. Source-of-Truth Hierarchy

When the documents disagree, use this order:

1. **This brief** for implementation decisions in this repo
2. [`omnicursor-team-guidance.md`](../../omnicursor-team-guidance.md) for demo-focused implementation details
3. Architecture diagrams in-repo: [`OMNICURSOR_SYSTEM_DESIGN.md`](./OMNICURSOR_SYSTEM_DESIGN.md) (capstone PDF/Pages deliverables are not stored in this repo).
4. Repo architecture and starter-kit constraints:
   - [`README.md`](../../README.md)
   - [`CLAUDE.md`](../../CLAUDE.md)
   - [`.cursor/rules/README.md`](../../.cursor/rules/README.md)
5. `omniclaude-main/` as a **reference library**, not a source of mandatory parity

If a current repo file contradicts the guidance and the newer architecture direction, prefer the guidance plus architecture direction, then update the implementation carefully.

---

## 3. Canonical OmniCursor Architecture

OmniCursor is a **Cursor-native adaptation of OmniClaude**, built from **rules, hooks, and a Python library** (plus file-backed skills):

1. **Cursor Rules**
   - Path: [`.cursor/rules/`](../../.cursor/rules)
   - Purpose: always-on and context-activated behavioral instructions
   - Role: the first routing surface and methodology surface

2. **Cursor Hooks**
   - Path: [`.cursor/hooks.json`](../../.cursor/hooks.json) and [`.cursor/hooks/`](../../.cursor/hooks)
   - Purpose: deterministic, non-LLM lifecycle behavior
   - Role: prompt routing, command guarding, edit-time diagnostics, session summarization

3. **Python library** (`src/omnicursor/`)
   - Path: [`src/omnicursor/`](../../src/omnicursor)
   - Purpose: structured agents/skills/compliance **for tests and CI**
   - Role: `get_agent_context`, skill loading, compliance checks; mirrors hook routing in `agents.py`

This is the architecture that was explicitly approved for the project.

---

## 4. What We Are Building Right Now

The current goal is a **demo-ready MVP vertical slice**, not full OmniClaude parity.

The MVP target is:

- rules remain the main behavioral layer
- hooks provide automatic behavior without requiring the LLM to decide to call library APIs
- the Python library provides structured payloads for tests and rubrics
- learned patterns can be persisted across sessions with the simplest viable mechanism first

### Demo-critical outcomes

The implementation should prioritize these outcomes:

1. A user prompt is automatically routed to the right agent behavior.
2. Risky shell commands are automatically guarded.
3. A learned pattern from session A can show up in session B.
4. If hooks are unavailable, rules + `skills/*.md` + the library still work for manual flows and CI.

---

## 5. Demo-Critical Implementation Priorities

Team guidance focuses on three areas because they map directly to demo success:

### A. Prompt enrichment

Target behavior:

- `on_prompt.py` should not just classify and log
- it should produce the context block or enrichment payload that makes routing visible and useful

This comes from the `format_injection()` pattern in the guidance doc.

### B. Pattern cache

Target behavior:

- store patterns in a simple JSON file first
- load matching patterns in `on_prompt.py`
- prove that a useful pattern survives across sessions

This comes from section 6 of the guidance doc.

### C. Routing upgrade

Target behavior:

- move beyond substring-only routing
- use the multi-strategy `TriggerMatcher` pattern
- add fuzzy matching and a confidence floor

This comes from section 2 of the guidance doc.

These are **implementation priorities**, not a demand to redesign the project.

---

## 6. What To Copy From OmniClaude

`omniclaude-main/` is useful, but only as a selective donor.

### Copy or adapt now

These parts map cleanly into OmniCursor:

| OmniClaude reference | OmniCursor destination | Why it matters |
|---|---|---|
| [`omniclaude-main/plugins/onex/hooks/lib/agent_router.py`](../../omniclaude-main/plugins/onex/hooks/lib/agent_router.py) | [`.cursor/hooks/on_prompt.py`](../../.cursor/hooks/on_prompt.py) and [`src/omnicursor/agents.py`](../../src/omnicursor/agents.py) | Core routing logic |
| [`omniclaude-main/plugins/onex/hooks/lib/context_injection_wrapper.py`](../../omniclaude-main/plugins/onex/hooks/lib/context_injection_wrapper.py) | [`.cursor/hooks/on_prompt.py`](../../.cursor/hooks/on_prompt.py) | Prompt enrichment formatting |
| [`omniclaude-main/plugins/onex/hooks/lib/bash_guard.py`](../../omniclaude-main/plugins/onex/hooks/lib/bash_guard.py) | [`.cursor/hooks/on_shell.py`](../../.cursor/hooks/on_shell.py) | Dangerous command guardrails |
| [`omniclaude-main/plugins/onex/hooks/lib/session_outcome.py`](../../omniclaude-main/plugins/onex/hooks/lib/session_outcome.py) | [`.cursor/hooks/on_stop.py`](../../.cursor/hooks/on_stop.py) | Better session summary and outcome tracking |
| [`omniclaude-main/plugins/onex/.claude/learned_patterns.json`](../../omniclaude-main/plugins/onex/.claude/learned_patterns.json) | `~/.omnicursor/learned_patterns.json` | Seed pattern persistence for MVP |
| [`omniclaude-main/plugins/onex/agents/configs/`](../../omniclaude-main/plugins/onex/agents/configs) | [`.cursor/agents/`](../../.cursor/agents) | Agent definitions and triggers |
| [`omniclaude-main/plugins/onex/skills/`](../../omniclaude-main/plugins/onex/skills) | [`skills/`](../../skills) | Reusable methodology skills |

### Do not copy wholesale

Do not try to port these areas into the MVP unless a narrow piece is required:

- Kafka event emission
- full PostgreSQL persistence
- Valkey as a hard dependency on day one
- Slack gates and notifications
- full agent observability stack
- all 50+ skills
- any workflow that assumes Claude Code-only lifecycle hooks not available in Cursor

### Porting rule

When borrowing from OmniClaude:

- copy the **shape and intent**
- simplify hard dependencies
- remove production infrastructure unless the demo needs it
- preserve small, explicit code over parity

---

## 7. Current Repo Constraints

These constraints matter when implementing:

- `omniclaude-main/` is read-only
- existing rules in [`.cursor/rules/`](../../.cursor/rules) are part of the architecture and should be preserved
- hooks currently live in [`.cursor/hooks/`](../../.cursor/hooks)
- Python library lives in [`src/omnicursor/`](../../src/omnicursor)
- skills live in [`skills/`](../../skills)
- `docs/ARCHITECTURE.md` is the starter-pack contract, not the whole OmniCursor implementation story

### Important implementation caveat

Some existing repo text still assumes `beforeSubmitPrompt` is informational-only.
The guidance doc assumes prompt enrichment is the desired target behavior.

That means OmniCursor should be built with this rule:

- **If Cursor supports prompt enrichment through hooks, use it**
- **If the current hook surface cannot mutate the prompt, keep the same routing logic and fall back to rules + reading `skills/*.md` for visible behavior**

Do not let that uncertainty block the architecture. Treat it as a capability gate, not a design reset.

---

## 8. MVP Build Order

Build in this order:

1. Preserve the current rules and library layout.
2. Upgrade `on_prompt.py` from logging-only to enrichment-ready routing.
3. Add JSON-backed learned pattern loading.
4. Upgrade routing to multi-strategy matching with confidence floor.
5. Improve `on_stop.py` with explicit session outcome classification.
6. Port the easiest OmniClaude methodology skills that fit Cursor directly.
7. Only then consider Valkey or PostgreSQL.

### Minimal acceptable MVP

The MVP is sufficient if it has:

- rules at repo root
- working hooks registered in [`.cursor/hooks.json`](../../.cursor/hooks.json)
- a real routing flow in `on_prompt.py`
- learned patterns persisted in JSON
- library APIs (`agents`, `skills`, `compliance`) that remain usable even without hooks

---

## 9. Copy Map: OmniClaude to OmniCursor

Use this mapping when copying structure:

| Concern | OmniClaude reference | OmniCursor target |
|---|---|---|
| prompt routing | `plugins/onex/hooks/lib/agent_router.py` | `.cursor/hooks/on_prompt.py`, `src/omnicursor/agents.py` |
| prompt enrichment formatting | `plugins/onex/hooks/lib/context_injection_wrapper.py` | `.cursor/hooks/on_prompt.py` |
| pattern storage seed | `plugins/onex/.claude/learned_patterns.json` | `~/.omnicursor/learned_patterns.json` |
| command safety | `plugins/onex/hooks/lib/bash_guard.py` | `.cursor/hooks/on_shell.py` |
| session outcome | `plugins/onex/hooks/lib/session_outcome.py` | `.cursor/hooks/on_stop.py` |
| agent manifests | `plugins/onex/agents/configs/*.yaml` | `.cursor/agents/*.json` or `.yaml` |
| methodology skills | `plugins/onex/skills/*/SKILL.md` | `skills/*.md` |

If a component in OmniClaude depends on Kafka, Slack, PostgreSQL, or internal ONEX services, treat it as a pattern to simplify, not as code to drop in directly.

---

## 10. What Not To Do

Avoid these failure modes:

- do not rewrite the project around library-only behavior in the IDE (hooks + rules matter)
- do not ignore the existing `.cursor/rules` starter kit
- do not try to port all of OmniClaude at once
- do not introduce Kafka, Qdrant, or full ONEX parity into the MVP
- do not make Valkey mandatory before JSON persistence works
- do not copy production complexity when a local file or in-memory structure proves the concept

---

## 11. Prompt Template For Future Implementation Work

Use this prompt when asking Cursor or Codex to implement more OmniCursor work:

```text
Use `docs/dev/OMNICURSOR_IMPLEMENTATION_BRIEF.md` as the primary implementation brief for this task.

Project context:
- OmniCursor is a Cursor-native adaptation of OmniClaude
- The approved architecture is Rules + Hooks + Python library (+ file-backed skills)
- `omnicursor-team-guidance.md` is the implementation guide for demo-critical pieces
- `omniclaude-main/` is a read-only reference that may be selectively adapted

Implementation rules:
- Preserve existing `.cursor/rules/*.mdc` unless a minimal change is required
- Prefer adapting structure from `omniclaude-main/` instead of inventing new architecture
- Keep the MVP local-first and minimal
- Do not add Kafka, Qdrant, Slack, or full ONEX infrastructure unless explicitly requested
- If borrowing from OmniClaude, cite the source file and explain how it maps into OmniCursor

Current priority:
- [replace this line with the concrete task]

Before coding:
1. inspect the relevant existing files
2. explain which OmniClaude files are relevant
3. explain whether the task belongs in Rules, Hooks, or the Python library

Then implement only the minimum coherent slice.

At the end, report:
1. files created
2. files modified
3. OmniClaude references reused
4. what now works
5. what remains next
```

---

## 12. One-Sentence Team Alignment

For OmniCursor, the architecture document defines the system, the team guidance doc defines the next implementation priorities, and `omniclaude-main/` is the reference library we selectively adapt to get the demo working fast.
