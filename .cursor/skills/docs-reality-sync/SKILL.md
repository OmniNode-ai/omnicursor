---
name: "onex:docs-reality-sync"
description: >-
  Use this skill when documentation has drifted from the codebase, needs an inventory, or should be archived.
disable-model-invocation: true
---

# onex:docs-reality-sync

Use this skill when documentation has drifted from the codebase, needs an inventory, or should be archived.

## Purpose

Keep README and `docs/` aligned with actual behavior: inventory, pick a source of truth, fix or archive stale material, then summarize actions.

## Workflow

1. Inventory `README.md` and `docs/`.
2. Establish source of truth from current codebase behavior.
3. Address drift (outdated paths, contradictions).
4. Archive superseded material when unmaintainable.
5. Summarize updates in a short table or bullet list.

## Quality checklist

- [ ] Inventory and source of truth stated
- [ ] Drift or outdated content addressed or archived
- [ ] Summary of actions for the reader
