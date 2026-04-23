---
name: writing-plans
description: >-
  Write bite-sized TDD-ordered implementation steps with exact file paths and acceptance criteria. Use when converting a design doc into a code-ready plan.
---

# Writing Plans

Use this skill when the user has a completed design doc and needs a comprehensive implementation plan with exact file paths, complete code examples, and a TDD approach.

## Purpose

Convert a validated design into a step-by-step implementation plan that any engineer can follow without prior codebase context. Each task is one action, 2-5 minutes of work.

## Prerequisites

- A completed design document (from brainstorming or provided inline)
- The design doc path (e.g., `docs/plans/YYYY-MM-DD-<topic>-design.md`) or pasted content

## Workflow

1. **Read the design document.**
   If a path is provided, read the design doc. If no design is provided, ask the user to provide it before proceeding.

2. **Write the plan header.**
   Every plan starts with: feature name, goal (one sentence), architecture (2-3 sentences), and tech stack.

3. **Break work into phases.**
   Each phase covers one component. Within each phase, tasks follow strict TDD order:
   - Write the failing test (complete code, not a placeholder)
   - Run the test to confirm it fails (exact command + expected error)
   - Write minimal implementation (complete code)
   - Run the test to confirm it passes (exact command)
   - Commit (exact git command)

4. **Ensure bite-sized granularity.**
   Each step is one action, 2-5 minutes. Never write "add validation logic" as a single step. Break into: write test, run, implement, verify, commit.

5. **Run adversarial review (R1-R6).**
   Before presenting the final plan, run these checks:
   - R1 — Count integrity: numeric quantifiers match actual list items
   - R2 — Acceptance criteria strength: no vague language, all measurable
   - R3 — Scope violations: each task can actually deliver what it claims
   - R4 — Integration traps: import paths, contract paths, API signatures verified
   - R5 — Idempotency: resource creation has dedup keys and rerun behavior
   - R6 — Verification soundness: each verification step graded strong/medium/weak

6. **Save the plan and hand off.**
   Save to `docs/plans/YYYY-MM-DD-<feature-name>.md`. Output the handoff line referencing the path and pointing to `12-plan-ticket`.

## Expected Output Format

A Markdown plan document with:
- Header (goal, architecture, tech stack)
- Phases with exact file paths (Create/Modify/Test)
- Complete code for each step (not pseudocode)
- Exact run commands with expected output
- Adversarial review summary (R1-R6)
- Handoff line with artifact path

## Quality Checklist

- [ ] Plan header includes goal, architecture, and tech stack
- [ ] Every step has exact file paths — no "somewhere in src/"
- [ ] Complete code provided — no "add validation here" placeholders
- [ ] TDD order followed: test first, then implementation
- [ ] Each step is one action, 2-5 minutes of work
- [ ] Adversarial review (R1-R6) was run and results documented
- [ ] Plan saved to `docs/plans/YYYY-MM-DD-<feature-name>.md`
- [ ] Handoff line references the actual saved artifact path
