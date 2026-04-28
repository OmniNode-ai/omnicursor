# Cursor vs Claude Code: Hook and Lifecycle Mapping

This document is the written deliverable for capturing how **OmniCursor** (Cursor-native) maps product lifecycle hooks to **Claude Code / OmniClaude-style** hooks, what parity exists, and where gaps matter for future work (Phase 3B, rubric evidence).

**Source of truth:** current repo behavior, then `cursor.md` and `docs/dev/HANDOFF.md`. The `omniclaude-main/` tree is a read-only reference for methodology patterns, not a mandate for API parity.

---

## 1. Vocabulary alignment

| Concept (OmniNode docs) | Typical Claude Code hook surface | OmniCursor in Cursor |
|------------------------|-----------------------------------|----------------------|
| **Session / lifecycle** | SessionStart, SessionEnd | No direct SessionStart hook in `.cursor/hooks.json`; session end approximated by **`stop`** |
| **User prompt** | UserPromptSubmit | **`beforeSubmitPrompt`** → `on_prompt.py` |
| **Tool / file boundaries** | PreToolUse, PostToolUse | **Partial:** `afterFileEdit` is edit-centric, not generic post-tool; **no** PreToolUse equivalent in current Cursor hooks config |
| **Shell** | (varies by host / product) | **`beforeShellExecution`** → `on_shell.py` (only hook that can **deny**) |

OmniCursor intentionally uses **Cursor’s** hook names and JSON stdin/stdout contract as defined for each event, not Claude’s event names.

---

## 2. Event matrix (implemented baseline)

| Cursor event (`hooks.json`) | Script | Stdin (representative) | Stdout contract | Blocking? | Primary purpose |
|-----------------------------|--------|-------------------------|-----------------|-----------|-----------------|
| `beforeSubmitPrompt` | `on_prompt.py` | JSON with `prompt`, `conversation_id`, `generation_id` | `{"systemMessage": "<!-- ... -->"}` | No (informational from product POV) | Classify prompt → agent name, score, reason; inject up to 5 **learned patterns** from `~/.omnicursor/learned_patterns.json` |
| `beforeShellExecution` | `on_shell.py` | JSON with command / metadata | `{"permission": "allow\|deny", ...}` | **Yes** (deny path) | Two-tier guard: HARD_BLOCK (deny), SOFT_WARN (allow + warning) |
| `afterFileEdit` | `on_edit.py` | JSON with edit paths | Informational | No | Diagnostic `ruff check` on `.py`; logs to `~/.omnicursor/events.jsonl` |
| `stop` | `on_stop.py` | JSON with session/status | Informational | No | Aggregate events, **4-gate** outcome (failed / success / abandoned / unknown), persist summary |

Supporting modules (not separate hook entries): **`_common.py`** (I/O, logging, agent JSON loading), **`pattern_loader.py`** (thread-safe pattern cache).

---

## 3. Mapping to “Claude-style” lifecycle hooks

This is a **conceptual** mapping for readers coming from OmniClaude terminology, not an API guarantee.

| OmniNode / Claude-style notion | OmniCursor equivalent | Parity |
|--------------------------------|----------------------|--------|
| SessionStart | *(none registered)* | **Gap** — any “bootstrap” logic lives in rules/docs, not a dedicated hook |
| UserPromptSubmit | `beforeSubmitPrompt` | **Strong** for classification + `systemMessage` emission |
| PreToolUse (inspect / gate before tools) | *(none)* | **Gap** — see §5 Phase 3B |
| PostToolUse | `afterFileEdit` only for edits | **Weak** — Edit-only, not “after every tool” |
| SessionEnd | `stop` | **Moderate** — Outcome classification and logging, not necessarily identical semantics to Claude SessionEnd |

---

## 4. `systemMessage` and platform uncertainty

`on_prompt.py` always writes valid JSON to stdout containing **`systemMessage`**: HTML-style comments with agent label, confidence, routing reason, and optional learned-pattern lines.

**Important:** Whether Cursor **injects** that `systemMessage` into the model context for every version and configuration is a **platform capability** question, not something this repo can hard-code. Treat prompt-time enrichment as **best-effort**. Operational guidance: verify behavior against your Cursor release; document outcomes for grading evidence (see rubric / Linear **OMN-40** as applicable).

---

## 5. Phase 3B (deferred): hooks named in planning docs

Future Cursor hook surfaces discussed for tightening parity include (names as commonly cited in project notes, not all guaranteed available in every product version):

| Candidate hook | Intent | Notes |
|----------------|--------|--------|
| `beforeMCPExecution` | Gate or log MCP tool calls | Would move toward **PreToolUse-like** observability |
| `beforeReadFile` | Gate or log file reads | Would support **bounded research** or audit narratives |

Until registered in `.cursor/hooks.json` and implemented, these are **design placeholders**, not OmniCursor behavior.

---

## 6. File map (quick reference)

| Path | Role |
|------|------|
| `.cursor/hooks.json` | Hook registration |
| `.cursor/hooks/on_prompt.py` | Routing + `systemMessage` + patterns |
| `.cursor/hooks/on_shell.py` | Shell guard |
| `.cursor/hooks/on_edit.py` | Ruff-on-edit |
| `.cursor/hooks/on_stop.py` | Stop / outcome |
| `.cursor/hooks/_common.py` | Shared helpers |
| `.cursor/hooks/pattern_loader.py` | Learned-pattern cache |
| `src/omnicursor/agents.py` | Same three-strategy scoring for library/tests path (`HARD_FLOOR = 0.55`) |

**Duplication note:** Hook code cannot import `src/omnicursor/`; scoring logic is mirrored between `on_prompt.py` and `agents.py` and must be kept aligned manually.

---

## Related docs

- [`ADR-hook-first-architecture.md`](./ADR-hook-first-architecture.md) — why hooks vs rules vs library (consolidation story)
- `cursor.md` — architecture and hook execution table
- [`HANDOFF.md`](./HANDOFF.md) — task history, demo criteria, known ambiguities
- `OmniCursor_DoD_Rubric.md` — observable verification (e.g. hook smoke tests, rubric §2)
