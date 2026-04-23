---
name: hostile-reviewer
version: 1.0.0
description: >-
  Adversarial multi-pass code review with iterative convergence. Loops until 2
  consecutive clean passes (no MINOR+ findings). Use before merging a PR or shipping
  a plan to catch structural issues before they reach production.
mode: both
tags:
  - review
  - adversarial
  - pr
  - plan
  - convergence
  - static-analysis
  - quality
  - risk
---

# Hostile Reviewer

**Announce at start:** "I'm using the hostile-reviewer skill."

## Description

Adversarial review with **iterative convergence**. A single pass catches ~60% of issues;
fixes from pass N introduce new issues caught in pass N+1. This skill loops until
**2 consecutive passes produce nothing above NIT severity**.

Cannot rubber-stamp. Output is MANDATORY — a `clean` verdict with an empty `findings`
array is valid, but the review must actually run.

## Modes

### PR Mode

Review a pull request diff.

```
/hostile-reviewer --pr <N> --repo <owner/repo>
```

Behavior:
- Review changed files plus high-risk neighbors.
- Produce severity-classified findings.
- Post structured review output when requested.

### File Mode

Review a plan or design document.

```
/hostile-reviewer --file <path>
/hostile-reviewer --plan-path <path>    # alias for --file
```

Behavior:
- Validate the target file exists before review.
- Review for logic gaps, missing constraints, and execution risk.

### Gate Mode

Merge-go/no-go decision. Dispatches 3 parallel review agents (scope, correctness,
conventions), collects structured verdicts, aggregates by severity, and produces a
structured `pass`/`fail` gate verdict.

```
/hostile-reviewer --pr <N> --repo <owner/repo> --gate
/hostile-reviewer --pr <N> --repo <owner/repo> --gate --strict
```

Requires `--pr` and `--repo`. Mutually exclusive with `--file`.

Gate verdict (`extra_status`):
- `passed`: no blocking findings across all agents
- `blocked`: one or more blocking findings (MAJOR+ default; MINOR+ with `--strict`)

### Static Mode

Static analysis sweep across source code without adversarial review.

```
/hostile-reviewer --static                          # full scan (first run = dry-run)
/hostile-reviewer --static --dry-run                # report only
/hostile-reviewer --static --ticket                 # create tickets for findings
/hostile-reviewer --static --repos <repo1,repo2>    # scope to specific repos
/hostile-reviewer --static --categories dead-code,stubs-shipped
/hostile-reviewer --static --max-tickets 5
```

**Finding Categories:**

1. **dead-code** — module-level unused functions/classes (LLM) + cross-file dead code (≥80% confidence)
2. **missing-error-handling** — bare `except:` / `except Exception:` with `pass`
3. **stubs-shipped** — `TODO`/`FIXME`/`NotImplementedError` in non-test source
4. **missing-kafka-wiring** — topics declared in contract.yaml but not wired in code
5. **schema-mismatches** — Pydantic field mismatches against contract config_keys
6. **hardcoded-values** — IP addresses, port numbers, connection strings in source
7. **missing-tests** — source modules with no corresponding test file

**State tracking**: `~/.omnicursor/code-review-state.json` tracks file hashes and finding
fingerprints to avoid re-scanning unchanged files and dedup across runs.

**First-run safety**: defaults to `--dry-run` unless explicitly overridden.

**Hard cap**: 10 tickets per run (configurable via `--max-tickets`).

## Convergence Algorithm

```
consecutive_clean = 0
pass_number = 0
max_passes = args.passes or 10  # safety cap

while consecutive_clean < 2 and pass_number < max_passes:
    pass_number += 1
    start_time = now()

    # 1. Run review
    result = run_review(mode, target)

    # 2. Count findings above NIT
    above_nit = [f for f in result.findings if f.severity in (CRITICAL, MAJOR, MINOR)]

    # 3. Record pass
    iteration_history.append({
        "pass": pass_number,
        "duration_s": elapsed(start_time),
        "verdict": result.verdict,
        "counts": {CRITICAL: ..., MAJOR: ..., MINOR: ..., NIT: ...},
        "action": "clean" if not above_nit else "fix_and_rerun"
    })

    # 4. Check convergence
    if not above_nit and result.verdict != "degraded":
        consecutive_clean += 1
    else:
        consecutive_clean = 0

    # 5. Apply fixes and loop
    if consecutive_clean < 2 and above_nit:
        apply_fixes(above_nit)

    if args.passes and pass_number >= args.passes:
        break
```

**Safety cap**: at most 10 passes. If convergence is not reached, report partial
convergence with full iteration history.

## Default Persona

All reviews use the **analytical-strict** persona:

- PhD-level domain expertise posture
- Journal-critique format: no praise, no qualifiers
- Contract-semantics focus: invariant gaps, integration boundary failures, missing idempotency guards
- Specific "what to change and why" per finding (three sentences max)
- Skeptical analytical tone: nothing assumed correct unless proven

## Severity Mapping

- **CRITICAL** — security, data loss, architectural redesign required
- **MAJOR** — incorrect behavior, missing error handling, serious test/performance gaps
- **MINOR** — quality, documentation, edge-case defects worth fixing pre-merge
- **NIT** — formatting, naming, minor style suggestions

## Output Format

### Per-Source Status

For each review source, report:
- Name / persona
- Status (succeeded / failed)
- Finding count by severity

### Disagreement Rendering

When sources materially disagree on a major issue (one flags CRITICAL/MAJOR, the other
is silent), surface that disagreement BEFORE the grouped findings:

```
DISAGREEMENT: Pass-1 analysis flags "Missing retry logic" as CRITICAL.
Pass-2 analysis did not flag this issue. Review the evidence below.
```

### Grouped Findings

Present findings grouped by severity:

```
## CRITICAL (1)

1. Missing retry logic on network boundary
   Evidence: ...
   Fix: ...

## MAJOR (2)
...
```

### Iteration History Table

ALWAYS include an iteration history table, even for single-pass runs:

```
## Iteration History

| Pass | Duration | Verdict        | CRIT | MAJ | MIN | NIT | Action        |
|------|----------|----------------|------|-----|-----|-----|---------------|
| 1    | 45.2s    | blocking_issue | 1    | 3   | 2   | 4   | fix_and_rerun |
| 2    | 38.7s    | risks_noted    | 0    | 1   | 1   | 2   | fix_and_rerun |
| 3    | 32.1s    | clean          | 0    | 0   | 0   | 1   | clean (1/2)   |
| 4    | 30.5s    | risks_noted    | 0    | 1   | 0   | 0   | fix_and_rerun |
| 5    | 29.8s    | clean          | 0    | 0   | 0   | 0   | clean (2/2)   |

Convergence: ACHIEVED after 5 passes (2 consecutive clean)
Total duration: 176.3s
Total findings resolved: 27
```

## Verdict Determination

**Per-pass verdict:**
- `clean` — no findings above MINOR; at least one review source succeeded; NIT-only is clean
- `risks_noted` — MAJOR findings exist but are not blocking
- `blocking_issue` — at least one CRITICAL finding; must fix before merge
- `degraded` — all review sources failed; no findings produced; NOT equivalent to `clean`

**Convergence verdict:**
- `converged` — 2 consecutive clean passes achieved
- `partially_converged` — max passes reached with fewer than 2 consecutive clean passes
- `not_converged` — fixed-pass mode (`--passes N`) completed without convergence; informational

## Failure Handling

- If one pass fails and another succeeds: report partial success, continue.
- If all sources fail: set verdict `degraded`; never silently report `clean`.
- Never hide failed pass attempts from output.

## Persisted Artifact

Write result to `~/.omnicursor/skill-results/{context_id}/hostile-reviewer.json`:

```json
{
  "mode": "pr|file",
  "target": "<pr_number or file_path>",
  "convergence_mode": "iterative|fixed",
  "passes_requested": null,
  "total_passes": 5,
  "consecutive_clean_at_end": 2,
  "convergence_verdict": "converged|partially_converged|not_converged",
  "iteration_history": [
    {
      "pass": 1,
      "duration_s": 45.2,
      "verdict": "blocking_issue",
      "counts": {"CRITICAL": 1, "MAJOR": 3, "MINOR": 2, "NIT": 4},
      "action": "fix_and_rerun"
    }
  ],
  "findings": [],
  "disagreements": [],
  "overall_verdict": "clean|risks_noted|blocking_issue|degraded"
}
```

`findings` and `disagreements` reflect the **final pass only**. Full per-pass breakdown
is in `iteration_history`.

Post result as a PR review comment (PR mode). For `blocking_issue`, use REQUEST_CHANGES;
otherwise use COMMENT.

## Static Mode Artifact

Write to `~/.omnicursor/skill-results/{context_id}/hostile-reviewer-static.json`:

```json
{
  "mode": "static",
  "run_id": "20260422-140000-a3f",
  "repos_scanned": 8,
  "files_scanned": 142,
  "files_skipped_unchanged": 87,
  "total_findings": 23,
  "new_findings": 8,
  "by_category": {
    "dead-code": 5,
    "missing-error-handling": 3,
    "stubs-shipped": 4,
    "missing-kafka-wiring": 2,
    "schema-mismatches": 1,
    "hardcoded-values": 3,
    "missing-tests": 5
  },
  "tickets_created": 8,
  "ticket_cap_hit": false,
  "status": "clean|findings|partial|error"
}
```

Status values:
- `clean` — zero findings
- `findings` — one or more findings, all reported
- `partial` — scan was interrupted or some repos failed
- `error` — scan could not complete

## Quality Checklist

- [ ] Mode was correctly selected from arguments
- [ ] Announced "I'm using the hostile-reviewer skill." at start
- [ ] Findings are actionable and severity-classified
- [ ] No rubber-stamping occurred (review actually ran)
- [ ] Iteration history table rendered
- [ ] Convergence rule (2 consecutive clean passes) enforced unless fixed-pass mode
- [ ] `degraded` verdict used when all sources failed (NOT `clean`)
- [ ] Final per-pass verdict and convergence verdict explicitly stated
- [ ] Artifact written to `~/.omnicursor/skill-results/`
