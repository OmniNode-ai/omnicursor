---
name: "onex:plan-ticket"
description: >-
  Use this skill when the user has a plan or task description and needs a ticket contract template with deterministic repo detection and YAML output.
disable-model-invocation: true
---

# onex:plan-ticket

Use this skill when the user has a plan or task description and needs a ticket contract template with deterministic repo detection and YAML output.

## Purpose

Generate a structured YAML ticket contract template that can be handed to a team's ticket creation workflow or used as input to Linear (Stage 2). The skill uses deterministic repo detection to pre-fill the target repository.

## Prerequisites

- A plan document path or task description from the user
- Access to README.md in the repository root (for repo detection)

## Workflow

1. **Bounded context read.**
   Announce and read README.md. Optionally list one directory relevant to the prompt. Follow `01-codebase-research` constraints.

2. **Deterministic repo detection (3-priority chain).**
   Determine which OmniNode repository this ticket belongs to:
   - **Priority 1 — CWD or prompt match:** Check if the working directory path or user's prompt contains one of the 7 valid repo names (case-insensitive substring). If found, use it.
   - **Priority 2 — README project name:** Check if README.md contains a valid repo name as the project name. If found, use it.
   - **Priority 3 — Ask the user:** If priorities 1 and 2 both fail, present a multiple-choice question listing all 7 repos plus "Other." Wait for the answer.

   Valid repos: `omniclaude`, `omnibase_core`, `omnibase_infra`, `omnidash`, `omniintelligence`, `omnimemory`, `omninode_infra`

3. **Generate the YAML ticket template.**
   Output a YAML contract template pre-filled with context:
   - Derive `title` from the user's prompt (imperative verb form)
   - Set `repo` to the detected repo name
   - Add requirements inferred from the prompt — mark uncertain fields as "FILL IN"
   - Include verification blocks (unit tests, lint)
   - Leave `relevant_files` empty if file paths are unknown

4. **Create the Linear ticket via MCP.**

   Tool names depend on the Linear MCP server configured in Cursor; do not assume a single transport.

   - **Common in this repo’s Cursor setup:** `list_teams` on the Linear plugin, then `save_issue` with `title`, `team` (name or id), and `description` (markdown combining requirements + verification).
   - **Older / OmniClaude-shaped docs** may say `tracker.list_teams` and `tracker.create_issue` with `teamId` — match that *semantics* using whatever parameters your MCP tools actually accept.

   If multiple teams exist and none is obvious, ask the user which team to use. Always list teams (or confirm a single team) before creating the issue. Report the created ticket URL to the user.

## Expected Output Format

A YAML contract template (shown in chat for review) containing:
- `title`: imperative description
- `repo`: detected repository name
- `requirements`: list with id, statement, rationale, acceptance criteria
- `verification`: list with id, title, kind, command, expected, blocking
- `context`: relevant_files, patterns_found, notes

Followed by the Linear ticket creation result.

## Quality Checklist

- [ ] Bounded context read was announced before file access
- [ ] Repo detection followed the 3-priority chain exactly
- [ ] YAML template is syntactically valid
- [ ] Title uses imperative verb form
- [ ] Requirements have specific, testable acceptance criteria
- [ ] Verification section includes at least unit tests and lint
- [ ] Teams were resolved (`list_teams` / `tracker.list_teams`, or equivalent) before create (`save_issue` / `tracker.create_issue`, or equivalent)
- [ ] Linear ticket URL is reported to the user
