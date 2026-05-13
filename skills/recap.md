---
name: "onex:recap"
description: >-
  Summarize the current Cursor session inline in chat.
disable-model-invocation: true
---

# onex:recap

Summarize the current Cursor session inline in chat.

## What to do

1. Read `~/.omnicursor/events.jsonl` — filter lines where `conversation_id` matches
   the value in `~/.omnicursor/sessions/current.json` (field: `conversation_id`).
   If the file is absent or the field is missing, use the most recent entries.

2. Read `~/.omnicursor/sessions/<conversation_id>.json` for outcome and aggregated stats.

3. Run `git log --oneline -5` and `git diff --name-only HEAD` for files in progress.

## Output format

Respond with this structure, inline in chat (do not write to any file):

## Session Recap
**Outcome:** success / failed / abandoned / unknown
**Files edited:** [list paths, or "none"]
**Shell commands:** N allowed, N warned, N denied
**Ruff findings:** N total across session
**Prompts classified:** N

## What happened
2–3 sentence narrative of what was worked on this session.

## Suggested next steps
- [Bullet 1 — based on what was in progress]
- [Bullet 2]
- [Bullet 3]
