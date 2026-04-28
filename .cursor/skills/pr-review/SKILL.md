# PR Review

Use this skill when reviewing a pull request for merge readiness. The goal is to produce a priority-organized assessment that clearly communicates what must be fixed before merge.

## Purpose

Systematically review all PR changes, classify issues by severity, and produce a merge readiness verdict. This ensures consistent review standards and prevents critical issues from reaching production.

## Prerequisites

- A PR number, branch with open changes, or a pasted diff / list of files to review
- Optional: `gh` CLI for `gh pr view` when you are working against GitHub; if unavailable, use local `git diff` / Cursor diffs instead

## Workflow

1. **Fetch PR context.**
   Run `gh pr view <number> --json title,body,files,reviews,comments` to gather the full picture. Read the changed files locally to understand the actual diff.

2. **Review each changed file.**
   For every modified file, check for: correctness, security issues, performance regressions, missing tests, breaking API changes, and code quality.

3. **Classify findings by priority.**
   Assign each finding exactly one severity level:
   - **CRITICAL** — Security vulnerabilities, data loss risks, crashes, breaking changes. Must fix before merge.
   - **MAJOR** — Performance problems, incorrect behavior, missing tests, significant quality issues. Should fix before merge.
   - **MINOR** — Code quality improvements, missing docs, edge cases, non-critical refactoring. Should address but not blocking.
   - **NIT** — Formatting, naming, minor style suggestions. Optional — can merge with nits remaining.

4. **Assess merge readiness.**
   The PR is merge-ready only when all CRITICAL, MAJOR, and MINOR issues are resolved. NITs do not block merge.

5. **Write the review summary.**
   Output a priority breakdown table, merge readiness verdict, and each finding grouped by severity with file path and description.

## Expected Output Format

A structured review containing:
- Priority breakdown table (count per severity level)
- Merge readiness verdict (ready / not ready)
- Findings grouped by severity (CRITICAL first, then MAJOR, MINOR, NIT)
- Each finding includes: file path, description, and suggested fix

## Quality Checklist

- [ ] All changed files were reviewed
- [ ] Findings use exactly one of CRITICAL / MAJOR / MINOR / NIT
- [ ] Merge readiness verdict is stated explicitly
- [ ] CRITICAL and MAJOR findings include a suggested fix
- [ ] No findings are left unclassified
