# Skill Translation Template

Use this template when porting an OmniNode SKILL.md to a Cursor `.mdc` rule.
Fill in every section. Leave no section empty — "N/A" is not acceptable.

---

## Template Structure

```markdown
---
description: [TRIGGERS — keywords that auto-activate this rule in Cursor]
globs:
alwaysApply: [true if always-on / false if trigger-activated]
---

# [Rule Name]

**Bucket [1/2/3] — [Bucket Name].** [One sentence on external deps.]

**Announce at start:** "[Exact announcement string]"

---

## Triggers

[List of exact phrases that activate this rule, e.g., "let's brainstorm", "write a plan"]

---

## Invariants

[Numbered list of non-negotiable behavioral constraints]

---

## Forbidden Patterns

[Numbered list of things this rule must never do]

---

## Output Format

[Description of the exact output structure: file names, headings, word counts]

---

## Handoff Sentence

[The exact handoff sentence template, with placeholders for date and topic]

---

## Test Prompt Reference

[Link to the test prompt file in tests/prompts/ that validates this rule]
```

---

## Required Invariants Section

Every ported rule must include an Invariants section. Required invariants for all Bucket 1 and Bucket 2 rules:

1. **One question per message.** A message that contains two or more questions is non-conformant.
2. **Announce before read.** Any file content used must be preceded by an announcement line naming that file.
3. **Deterministic handoff.** The handoff sentence must reference the saved artifact path, not "paste above" or a paraphrase.
4. **Bounded research only.** File reads limited to: README.md, cursor.md, docs/INDEX.md, and one named directory listing.
5. **No phantom callables.** Do not reference helper functions, validators, or APIs that are not real tools available in Cursor.

Additional invariants may be added per skill but cannot remove the above.

---

## Forbidden Patterns Section

Every ported rule must include a Forbidden Patterns section. Required forbidden patterns:

| Pattern | Why Forbidden |
|---------|--------------|
| Two or more questions in one message | Overwhelms the user; rubric auto-fail |
| "scan everything" or recursive search | Non-deterministic; different repos produce different behavior |
| "paste above" in handoff | Breaks the artifact-path-anchored handoff protocol |
| Vague verification ("tests pass") | Rubric requires testable, specific criteria |
| Phantom callables (`call validate_contract()`) | The function doesn't exist in Cursor; rule becomes untestable |
| Non-deterministic repo detection | Any variation from the 3-priority chain is non-conformant |
| Absolute paths in output (`/Volumes/...`) | Students don't have access to your machine's paths |
| External service calls in Bucket 1/2 rules | Bucket boundary violation |

---

## Output Format Constraints

### Design Files (from brainstorming)
- **Location:** `docs/plans/YYYY-MM-DD-<topic>-design.md`
- **Section word count:** 200–300 words per design section
- **Required sections:** Architecture, Components, Data Flow, Error Handling, Testing Strategy
- **Check-in:** One check-in question after each section (counts as the one allowed question)

### Plan Files (from writing-plans)
- **Location:** `docs/plans/YYYY-MM-DD-<feature>.md`
- **Header:** Exact header block from `11-writing-plans.mdc`
- **Task granularity:** Each step is one action, 2–5 minutes
- **Code:** Complete, not placeholder ("add validation" is forbidden)
- **Commands:** Exact commands with expected output

### Ticket Templates (from plan-ticket)
- **Format:** YAML only — no prose descriptions above the YAML block
- **Required fields:** `title`, `repo`, `requirements[]`, `verification[]`, `context`
- **Repo field:** One of the 7 valid repo names, detected via 3-priority chain

---

## Handoff Sentence Format

The handoff sentence must follow this exact template:

```
**Next step**: In Cursor Composer, invoke rule `<rule-name>` and provide the path `<artifact-path>` as context.
```

Where:
- `<rule-name>` is the exact MDC filename without extension (e.g., `11-writing-plans`)
- `<artifact-path>` is the actual path written, including the date and slug

The rule fills in `<artifact-path>` when it writes the file. This cannot be a generic
placeholder like `<path-to-design>` — it must be the real path.

---

## Correctness Rubric (Pass/Fail Checklist)

Use this checklist to self-grade a ported rule before submitting:

### Triggers Section
- [ ] `description` field in MDC frontmatter contains at least 3 trigger phrases
- [ ] Trigger phrases match natural language a student would type (not OmniNode jargon)

### Invariants Section
- [ ] All 5 required invariants present
- [ ] Invariants are stated as constraints, not guidelines ("must" not "should")

### Forbidden Patterns Section
- [ ] All 8 required forbidden patterns listed
- [ ] Each pattern has a "why forbidden" explanation

### Output Format Section
- [ ] File location is a relative path (no `/Volumes/` or absolute paths)
- [ ] Word counts or size constraints are specified
- [ ] Required fields/sections are listed explicitly

### Handoff Sentence
- [ ] Handoff sentence uses the exact template format
- [ ] Rule fills in the actual path (not a placeholder) at the time of writing

### Test Prompt Reference
- [ ] At least one test prompt file is referenced
- [ ] The referenced prompt file exists in `tests/prompts/<rule-name>/`

### Rubric Compatibility
- [ ] Rule can be evaluated against the corresponding rubric in `tests/rubrics/`
- [ ] No rubric criterion is left unaddressable by the rule's behavior
