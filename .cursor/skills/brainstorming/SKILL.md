---
name: brainstorming
description: >-
  Refine rough ideas into 2-3 design approaches with named trade-offs, ending with a design doc. Use when someone wants to explore a feature or says 'let's brainstorm' before writing code.
---

# Brainstorming

Use this skill when the user has a rough idea, wants to explore a feature, or says "let's brainstorm" or "help me design." The goal is to refine an idea into a validated design doc before any code is written.

## Purpose

Transform vague ideas into fully-formed designs through collaborative dialogue. This skill ensures alignment on what to build before committing to how to build it.

## Prerequisites

- A rough idea or feature request from the user
- Access to the repository root (for bounded context via `01-codebase-research`)

## Workflow

1. **Bounded context check.**
   Announce what you will read before reading anything. Follow the `01-codebase-research` rule. Read only README.md, CLAUDE.md, and one relevant directory listing.

2. **Clarify with one question at a time.**
   Ask questions to understand purpose, constraints, success criteria, and affected components. Only one question per message. Prefer multiple-choice when the answer space is finite. Stop asking when you have enough context to propose approaches.

3. **Propose 2-3 approaches with trade-offs.**
   Present each approach with a name, pros, cons, and a clear recommendation with a one-sentence rationale. Apply YAGNI — remove features not needed for the stated goal.

4. **Present design in 200-300 word sections.**
   After an approach is chosen, present the design incrementally. After each section, ask "Does this look right so far?" and wait for confirmation. Cover: architecture, components, data flow, error handling, testing strategy.

5. **Write the design file.**
   Save the validated design to `docs/plans/YYYY-MM-DD-<topic>-design.md` using today's date and a kebab-case topic slug.

6. **Hand off with artifact path.**
   Output the exact handoff line referencing the saved file path:
   `**Next step**: In Cursor Composer, invoke rule 11-writing-plans and provide the path docs/plans/YYYY-MM-DD-<topic>-design.md as context.`

## Expected Output Format

A Markdown design document saved to `docs/plans/` containing:
- Problem statement
- Constraints and scope
- Chosen approach with rationale
- Architecture overview
- Component breakdown
- Data flow description
- Error handling strategy
- Testing strategy

## Quality Checklist

- [ ] Announcement line appears before any file content is used
- [ ] Every question message contains exactly one question
- [ ] At least 2 approaches with named trade-offs were presented
- [ ] Design was presented in 200-300 word sections with check-ins
- [ ] Design file saved to `docs/plans/YYYY-MM-DD-<topic>-design.md`
- [ ] Handoff line references the actual saved artifact path
