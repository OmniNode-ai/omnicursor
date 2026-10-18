# Rubric: Plan Ticket Rule (`12-plan-ticket.mdc`)

**Bucket:** 2 — Local-Data Hybrid
**Grading mode:** Pass/Fail — all criteria must pass

---

## Repo Detection (3-Priority Chain)

The repo detection algorithm must follow the exact chain specified in `.cursor/rules/12-plan-ticket.mdc`.

### Priority 1 — CWD or Prompt Match

- [ ] **D1a** — When the prompt contains a valid repo name (e.g., "in omniclaude"), the rule uses that repo without asking
- [ ] **D1b** — The rule does NOT ask a clarifying question when Priority 1 resolves successfully
- [ ] **D1c** — Priority 1 uses substring matching (case-insensitive) — "omnibase_core" in "add caching to omnibase_core" resolves correctly

**Test with:** `tests/prompts/plan-ticket/01-simple.md` (repo explicit in prompt)

### Priority 2 — README Project Name

- [ ] **D2a** — When Priority 1 fails AND README.md contains a valid repo name as project name, the rule uses that repo
- [ ] **D2b** — The rule reads README.md (with announcement) before falling through to Priority 3

### Priority 3 — Ask User

- [ ] **D3a** — When both Priority 1 and 2 fail, the rule asks exactly ONE multiple-choice question
- [ ] **D3b** — The question lists all 7 valid repo options plus "Other"
- [ ] **D3c** — The question is multiple-choice (labeled A–H), not a free-text prompt
- [ ] **D3d** — The rule waits for the user's answer before generating the template (does NOT guess)

**Test with:** `tests/prompts/plan-ticket/02-ambiguous-repo.md` (no repo in prompt or README)

---

## Template Output Format

- [ ] **T1** — Output is a single YAML code block (not prose with embedded YAML)
- [ ] **T2** — Required fields present: `title`, `repo`, `requirements[]`, `verification[]`, `context`
- [ ] **T3** — `repo` field contains one of the 7 valid repo names (not a placeholder like "FILL IN")
- [ ] **T4** — At least one requirement is inferred from the prompt (not all fields left as "FILL IN")
- [ ] **T5** — `verification[]` contains at least one entry with `command` and `expected` fields
- [ ] **T6** — No absolute paths appear in the output (no `/Volumes/...`, no `/home/...`)

---

## Bounded Research

- [ ] **B1** — Rule announces what it reads before using file content: `Reading: README.md | Listing: <dir/>`
- [ ] **B2** — Rule reads at most README.md + one directory listing
- [ ] **B3** — Rule does not read test files, all source files, or perform recursive search

---

## Handoff

- [ ] **H1** — Handoff line references the `linear` rule (not a generic "next step")
- [ ] **H2** — Handoff acknowledges this is a Stage 2 operation (requires Linear MCP)

---

## Scoring

| Category | Criteria | Met |
|----------|----------|-----|
| Repo detection | 7 criteria | ___ / 7 |
| Template format | 6 criteria | ___ / 6 |
| Bounded research | 3 criteria | ___ / 3 |
| Handoff | 2 criteria | ___ / 2 |

**Final:** PASS (all 18 criteria met) OR FAIL (any criterion not met)

---

## Grading Notes

- **Ambiguous prompt test:** For `02-ambiguous-repo.md`, if the grader answers "B) omnibase_core" to the repo question, the generated template must have `repo: "omnibase_core"`. If it has a different repo, D3d fails.
- **Priority ordering:** If a rule skips Priority 1 (checks README first even when prompt has the repo name), it fails D1a even if the final answer is correct.
- **No guessing:** A rule that outputs a template with `repo: "omniclaude"` without asking when the prompt says "add caching" (no repo mentioned) fails D3d regardless of whether omniclaude was a reasonable guess.
