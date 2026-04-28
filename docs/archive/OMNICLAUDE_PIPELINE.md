# OmniClaude Automation Pipeline

How a typical session flows from ticket to merged PR, covering skills, agent delegation, and nightly orchestration.

---

## The Core Loop: One Ticket → Merged PR

Everything starts with `/ticket-pipeline OMN-1234`. It is a state machine FSM with 8 sequential phases and a circuit breaker (3 consecutive failures → halt):

```
PRE_FLIGHT → IMPLEMENT → LOCAL_REVIEW → CREATE_PR
    → TEST_ITERATE → CI_WATCH → PR_REVIEW → AUTO_MERGE
```

### Phase Breakdown

| Phase | What happens |
|-------|-------------|
| **PRE_FLIGHT** | Load ticket contract from Linear, validate repo target, check environment |
| **IMPLEMENT** | Delegates to `/ticket-work` — reads relevant code, surfaces clarifying questions (human gate, skippable with `--autonomous`), writes implementation spec back to the Linear ticket description, then executes code in a git worktree, runs tests and pre-commit |
| **LOCAL_REVIEW** | Runs local-review skill until N consecutive clean passes (lint, type errors, logic issues caught before CI) |
| **CREATE_PR** | `gh pr create` + enable GitHub auto-merge |
| **TEST_ITERATE** | Polls CI for test failures, fixes them locally, pushes, re-polls up to max-iterations cycles |
| **CI_WATCH** | Polls GitHub Actions until green or wall-clock timeout |
| **PR_REVIEW** | Delegates to `/hostile-reviewer` (multi-model adversarial review) — posts findings as PR comments, returns a merge-readiness verdict: `clean`, `risks_noted`, or `blocking_issue` |
| **AUTO_MERGE** | CDQA gate check → poll CI readiness → `gh pr merge` → close Linear ticket → delete branch |

The Linear ticket transitions automatically: **In Progress → In Review → Done**.

---

## Skills in Detail

### `/ticket-work`

Called by `ticket-pipeline` Phase 2. Handles the full implementation cycle with 7 internal phases:

```
INTAKE → RESEARCH → QUESTIONS → SPEC → IMPLEMENT → REVIEW → DONE
```

- **INTAKE**: Fetch ticket, parse contract, validate repo
- **RESEARCH**: Read existing code and relevant implementations
- **QUESTIONS**: Surface blockers as questions — human gate (skipped with `--autonomous`)
- **SPEC**: Write implementation spec into the Linear ticket description
- **IMPLEMENT**: Write code in a git worktree, run tests, pass pre-commit
- **REVIEW**: Run local-review, address findings
- **DONE**: Return control to `ticket-pipeline` FSM

Writes a `ModelSkillResult` JSON to `$ONEX_STATE_DIR/skill-results/{context_id}/ticket-work.json`.

---

### `/pr-review` (via `/hostile-reviewer`)

Called by `ticket-pipeline` Phase 7. Runs multi-model adversarial review:

- Optional seam contract pre-gate (if ticket has a contract)
- Posts severity-classified findings as PR comments: CRITICAL, MAJOR, MINOR, NIT
- Returns merge-readiness verdict to the FSM
- Iterates to convergence: 2 consecutive clean passes before declaring stable

---

### `/auto-merge`

Called by `ticket-pipeline` Phase 8:

1. CDQA gate check (mandatory — contract compliance + CI gates)
2. Poll `mergeStateStatus == "CLEAN"` every 60s (24h wall-clock budget)
3. `gh pr merge --squash`
4. Close Linear ticket via `tracker.save_issue()`
5. Delete branch

---

## Scale: Multi-PR with `/merge-sweep`

To drain a backlog of open PRs across repos, `/merge-sweep` runs two tracks in parallel. Typically invoked on a cron (`cron-merge-sweep.sh`) to clear the queue overnight.

### Track A — Merge-ready PRs
CI green, approved, no conflicts → enable GitHub auto-merge immediately.

### Track B — Fixable PRs
CI failures, conflicts, or changes-requested → dispatch a `/pr-polish` agent per PR:

1. Resolve merge conflicts (`gh pr update-branch`)
2. Address all review comments and CI failures
3. Iterate local-review until N consecutive clean passes
4. Enable auto-merge

```
/merge-sweep
    ├─ Track A: already clean → queue auto-merge
    └─ Track B: broken → /pr-polish per PR
                            ├─ resolve conflicts
                            ├─ fix CI / review comments
                            ├─ local-review loop
                            └─ enable auto-merge
```

Returns: `queued | nothing_to_merge | partial | error`

---

## Nightly Orchestrator: `/onex:session`

`/onex:session` (formerly `/autopilot`, deprecated OMN-8340) runs the full nightly close-out across the org. Each phase runs as a fresh `claude -p` invocation with its own context window. Results are checkpointed so a Phase B failure does not lose Phase A work.

### Phase A — Prepare (sequential)

| Step | Action |
|------|--------|
| A0 | `/worktree --prune --execute` — GC merged worktrees |
| A1 | `/merge-sweep` — full PR queue drain |
| A1b | dirty-PR triage via `/pr-polish` |
| A2 | deploy local plugin |
| A3 | start environment (infra audit-first startup) |

### Phase B — Quality Gate

B1–B4 run in parallel; B5–B6 are hard gates that halt the pipeline on failure.

| Step | Check | Gate type |
|------|-------|-----------|
| B1 | DoD sweep — DoD compliance per ticket | Advisory |
| B2 | AI anti-pattern sweep | Advisory |
| B3 | Kafka topic health audit | Advisory |
| B4 | Gap detect — cross-repo integration gaps | Advisory |
| B5 | Integration sweep | **HARD GATE** |
| B6 | Playwright regression | **HARD GATE** |

### Phase C — Ship (sequential)

| Step | Action |
|------|--------|
| C1 | Release — version bump + publish |
| C2 | Redeploy — runtime refresh |

### Phase D — Verify

D1–D3 run in parallel; D4 is sequential.

| Step | Action |
|------|--------|
| D1 | Verify plugin |
| D2 | Container health |
| D3 | Dashboard sweep |
| D4 | Close-day audit artifact |

---

## Full Picture

```
Linear Ticket
    │
    ▼
/ticket-pipeline              ← one ticket, sequential FSM
    │
    ├─ /ticket-work           ← implementation in worktree
    │       └─ (human gate skippable with --autonomous)
    ├─ /hostile-reviewer      ← multi-model adversarial PR review
    └─ /auto-merge            ← CI gate + merge + close ticket


/merge-sweep                  ← org-wide cron, parallel across all PRs
    ├─ Track A: auto-merge    (already clean)
    └─ Track B: /pr-polish    (fix → re-review → merge)


/onex:session                 ← nightly orchestrator
    ├─ Phase A: worktree GC + merge-sweep drain
    ├─ Phase B: quality gates (integration tests, DoD sweep)
    ├─ Phase C: release + redeploy
    └─ Phase D: verify + close-day audit
```

---

## Key Design Principles

- **Structured handoffs**: every skill writes a `ModelSkillResult` JSON — the next phase reads it, not free-form output. No implicit state passing.
- **`--autonomous` flag**: skips all human gates throughout `ticket-work` for fully headless runs.
- **Circuit breakers**: every FSM halts after 3 consecutive failures and writes a diagnostic before wasting further compute.
- **Linear as source of truth**: ticket status (`In Progress → In Review → Done`) updates flow automatically at each phase transition.
- **Fresh context windows**: nightly orchestrator phases run as separate `claude -p` invocations — no single context window accumulates across the full pipeline.
- **Hard vs advisory gates**: only integration sweep and Playwright block the release; everything else in Phase B is advisory.

---

## See Also

- `omniclaude-main/plugins/onex/skills/ticket_pipeline/SKILL.md` — FSM spec and phase contract
- `omniclaude-main/plugins/onex/skills/ticket_work/SKILL.md` — implementation workflow
- `omniclaude-main/plugins/onex/skills/merge_sweep/SKILL.md` — PR lifecycle orchestration
- `omniclaude-main/plugins/onex/skills/hostile_reviewer/SKILL.md` — adversarial review spec
- `omniclaude-main/plugins/onex/skills/auto_merge/SKILL.md` — CDQA gate and merge logic
