# Hostile Reviewer

Use this skill for multi-pass adversarial review of PRs or plan files. It is intentionally skeptical, cannot rubber-stamp, and must iterate until convergence or safety cap.

## Start Message

At the beginning of every run, explicitly state:
"I'm using the hostile-reviewer skill."

## Description

Perform adversarial review with iterative convergence. A single pass is incomplete by default; fixes from pass N can introduce new issues found in pass N+1. The reviewer must run multiple passes and require two consecutive clean passes before declaring stability.

## Modes

### PR Mode

Use when reviewing a pull request diff.

Inputs:
- `pr`: PR number
- `repo`: repository slug (required with `pr`)

Behavior:
- Review changed files plus high-risk neighbors.
- Produce severity-classified findings.
- Post structured review output when requested.

### File Mode

Use when reviewing a plan or design document.

Inputs:
- `file` (or alias `plan-path`)

Behavior:
- Validate the target file exists before review.
- Review for logic gaps, missing constraints, and execution risk.

### Gate Mode

Use for merge-go/no-go decisions.

Inputs:
- `pr` + `repo` + `gate`
- Optional `strict`

Behavior:
- Default blocking threshold: MAJOR+
- Strict threshold: MINOR+
- Return gate verdict: `passed` or `blocked`

### Static Mode

Use for static-analysis sweeps across source code.

Input:
- `static`
- Optional: `repos`, `categories`, `dry-run`, `ticket`, `max-tickets`

Finding categories:
1. dead-code
2. missing-error-handling
3. stubs-shipped
4. missing-kafka-wiring
5. schema-mismatches
6. hardcoded-values
7. missing-tests

## Severity Mapping

- **CRITICAL**: security, data loss, or redesign-level defects
- **MAJOR**: incorrect behavior, missing error handling, serious test/perf gaps
- **MINOR**: quality/documentation/edge-case defects worth fixing pre-merge
- **NIT**: style and naming suggestions only

## Convergence Rules

Default behavior is iterative convergence:

1. Run one full review pass.
2. Count findings above NIT (CRITICAL/MAJOR/MINOR).
3. If above-NIT findings exist, apply fixes and rerun.
4. Clean pass = no findings above NIT and not degraded.
5. Converged = 2 consecutive clean passes.
6. Safety cap = maximum 10 passes.

If `passes` is provided, run fixed-count mode and report final state even if not converged.

## Reviewer Persona

Use analytical-strict posture:
- findings-first, no praise
- contract/invariant-aware
- integration-boundary-focused
- three-sentence maximum per finding whenever possible
- every finding includes a concrete change recommendation

## Required Output

Every result must include:

1. Per-model/per-source status (when applicable)
2. Findings grouped by severity
3. Iteration history across passes
4. Convergence status
5. Final verdict

Final verdict values:
- `clean`
- `risks_noted`
- `blocking_issue`
- `degraded`

Convergence verdict values:
- `converged`
- `partially_converged`
- `not_converged`

## Iteration History Format

Always include an iteration history table, even for single-pass runs:

```markdown
## Iteration History

| Pass | Duration | Verdict        | CRIT | MAJ | MIN | NIT | Models       | Action        |
|------|----------|----------------|------|-----|-----|-----|--------------|---------------|
| 1    | 45.2s    | blocking_issue | 1    | 3   | 2   | 4   | codex, dr1   | fix_and_rerun |
| 2    | 38.7s    | risks_noted    | 0    | 1   | 1   | 2   | codex, dr1   | fix_and_rerun |
| 3    | 32.1s    | clean          | 0    | 0   | 0   | 1   | codex, dr1   | clean (1/2)   |
| 4    | 30.5s    | clean          | 0    | 0   | 0   | 0   | codex, dr1   | clean (2/2)   |

Convergence: achieved after 4 passes.
Total findings resolved: 17
```

## Disagreement Reporting

If major model disagreement exists (one model flags CRITICAL/MAJOR and another is silent), report that disagreement before detailed findings.

## Failure Handling

- If one model fails and another succeeds: mark partial success and continue.
- If all models fail: set verdict `degraded`; do not silently report `clean`.
- Never hide failed model attempts from output.

## Quality Checklist

- [ ] Mode was correctly selected from arguments
- [ ] Findings are actionable and severity-classified
- [ ] No rubber-stamping occurred
- [ ] Iteration history was rendered
- [ ] Convergence rule (2 clean passes) enforced unless fixed-pass mode
- [ ] Final verdict and convergence verdict explicitly stated
