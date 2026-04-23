# OmniClaude Skills Reference

**Plugin**: `omniclaude` → `plugins/onex/skills/`
**Last Updated**: 2026-02-25
**Total Skills**: ~53 primary + nested sub-skills under `agent-tracking/` and `system-status/`

**OmniCursor note:** This inventory describes **OmniClaude only**. OmniCursor intentionally ships a **small curated** skill set (on the order of **~12–17** methodology skills) and grows **only when needed** — see [docs/OMNICURSOR_MIGRATION_PLAN.md](./docs/OMNICURSOR_MIGRATION_PLAN.md).

This document is the canonical reference for every skill available in the OmniClaude plugin. Skills are invoked via `/skill-name` in Claude Code or composed as sub-skills by orchestrators.

---

## Table of Contents

1. [Workflow Orchestration](#1-workflow-orchestration)
2. [CI/CD & Deployment](#2-cicd--deployment)
3. [Code Review & Pull Requests](#3-code-review--pull-requests)
4. [Architecture & Quality](#4-architecture--quality)
5. [Observability & Diagnostics](#5-observability--diagnostics)
6. [Planning & Design](#6-planning--design)
7. [State & Recovery](#7-state--recovery)
8. [Ticketing & Linear Integration](#8-ticketing--linear-integration)
9. [Supporting Infrastructure](#9-supporting-infrastructure)
10. [Advanced & Parallel Execution](#10-advanced--parallel-execution)
11. [Shared Libraries & Helpers](#11-shared-libraries--helpers)
12. [Architectural Patterns](#12-architectural-patterns)

---

## 1. Workflow Orchestration

### `ticket-pipeline` (v5.0.0)
Autonomous per-ticket pipeline that chains the full delivery lifecycle from implementation through merge.

**Phases**: `pre_flight → implement → local_review → create_pr → ci_watch → pr_review_loop → auto_merge`

**Key features**:
- Policy-driven auto-advance (not agent judgment) — each phase transition is governed by explicit policy switches
- Auto-detection: resumes from last checkpoint state if a run was interrupted
- Cross-repo splitting via `decompose-epic` for multi-repo tickets
- Ticket-run ledger prevents duplicate runs on the same ticket
- Slack lifecycle notifications at each phase boundary
- Dry-run mode (`--dry-run`) for previewing without side effects

**Arguments**: `ticket_id`, `--skip-to <phase>`, `--dry-run`, `--force-run`, `--auto-merge`

**Composed sub-skills**: `ticket-work`, `local-review`, `ci-watch`, `pr-watch`, `auto-merge`, `slack-gate`, `checkpoint`

---

### `epic-team` (v2.0.0)
Orchestrate a Claude Code agent team to autonomously work a Linear epic across multiple repos.

**Key features**:
- Thin orchestrator — delegates all execution to sub-skills, never implements directly
- Auto-decomposes empty epics via `decompose-epic` before dispatch
- Per-ticket worker spawning as `Task` subagents
- State persistence in `~/.claude/epics/{epic_id}/state.yaml`
- Slack lifecycle notifications (on start, each ticket completion, epic done)
- `--resume` flag to continue from last known state after a crash

**Arguments**: `epic_id`, `--dry-run`, `--force`, `--force-kill`, `--resume`, `--force-unmatched`

**Composed sub-skills**: `decompose-epic`, `slack-gate`, `ticket-pipeline`

---

### `ticket-work`
Implementation phase executor for autonomous ticket work within the pipeline.

**Key features**:
- Autonomous mode (no human delegation mid-execution)
- Cross-repo file tracking across worktrees
- Reports files changed, tests run, and any blockers encountered

---

### `decompose-epic` (v1.0.0)
Analyze a Linear epic description and create sub-tickets as Linear children.

**Key features**:
- Repo manifest keyword-to-repo mapping (infers which repos are affected from the epic text)
- Creates one sub-ticket per distinct work area
- Outputs `ModelSkillResult` JSON with the created ticket list for parent orchestrators

**Arguments**: `epic_id`, `--dry-run`

---

### `local-review` (v2.0.0)
Local code review loop that iterates through review → fix → commit cycles without pushing.

**Key features**:
- **Phase 0**: Pre-existing issue scan — auto-fixes low-risk violations, defers others with a note
- Keyword-based priority classification: `CRITICAL / MAJOR / MINOR / NIT`
- Consecutive clean run confirmation (default: 2 consecutive clean passes required)
- Per-session audit trail written to `~/.claude/review-notes/`
- Retry policy: up to 2 retries on agent or parse failures
- Auto-dispatches `systematic-debugging` when a fix attempt fails

**Arguments**: `--uncommitted`, `--since <sha>`, `--max-iterations <n>`, `--files <glob>`, `--no-fix`, `--no-commit`, `--checkpoint`, `--required-clean-runs <n>`, `--path <dir>`

---

### `checkpoint` (v1.0.0)
Pipeline checkpoint management for resume, replay, and phase validation.

**Storage**: `~/.claude/checkpoints/{ticket_id}/{run_id}/phase_{N}_{name}_a{attempt}.yaml`

**Key features**:
- Append-only writes (never overwrites existing checkpoints)
- Phase ordinals: `1=implement`, `2=local_review`, `3=create_pr`, `4=ready_for_merge`
- Structural validation: schema, path, format, timestamp
- Used by `ticket-pipeline` to survive session crashes

**Operations**: `write`, `read`, `validate`, `list`

**Arguments**: `operation`, `--ticket-id`, `--run-id`, `--phase`, `--attempt`, `--repo-commit-map`, `--artifact-paths`, `--payload`

---

## 2. CI/CD & Deployment

### `ci-failures` (v1.0.0)
Fetch and analyze GitHub Actions CI failures with severity classification.

**Key features**:
- Two-tier investigation: quick-review (default) → deep-dive on demand
- Severity classification: `CRITICAL / MAJOR / MINOR`
- Flaky test detection based on error patterns
- 5-minute caching to avoid redundant API calls
- JSON and Markdown output modes

**Sub-commands**:
- `ci-quick-review` — one-command summary (recommended starting point)
- `get-ci-job-details <job-id>` — deep-dive into a specific job
- `fetch-ci-data` — raw CI data (advanced/scripting use)

---

### `ci-fix-pipeline` (v1.0.0)
Autonomous CI failure fix pipeline. Fetches failures, classifies, fixes, and commits.

**Flow**: fetch CI failures → Slack start notification → classify by scope → sub-ticket large-scope failures → fix all → commit → Slack complete

**Key features**:
- Skip patterns for selective exclusion of known-unfixable failures
- Sub-ticket creation for large-scope failures (more than `max_fix_files` files affected)
- Architectural failure changes require explicit Slack approval gate before proceeding
- Outputs `ModelSkillResult` JSON for parent pipeline orchestrators

**Policy defaults**: `fix_all: true`, `max_fix_files: 10`, `fix_preexisting_in_touched: true`

**Arguments**: `--pr`, `--branch`, `--skip-patterns`, `--max-fix-files`, `--no-slack`, `--ticket-id`

---

### `ci-watch` (v1.0.0)
Poll GitHub Actions CI for a PR, auto-fix failures, and report terminal state.

**Key features**:
- Uses `gh run watch` (event-driven, not polling) — waits for CI completion signal
- Auto-fix via `ci-fix-pipeline` on failure detection
- Fix cycle cap (default: 3 cycles before declaring `capped`)
- Terminal states: `passed`, `capped`, `timeout`, `error`

**Arguments**: `pr_number`, `repo`, `--timeout-minutes`, `--max-fix-cycles`, `--no-auto-fix`

---

### `auto-merge` (v1.0.0)
Merge a GitHub PR when all gates pass, using a Slack `HIGH_RISK` gate by default.

**Key features**:
- `HIGH_RISK` Slack gate — requires an explicit "merge" reply; silence ≠ consent
- Merge strategies: `squash` | `merge` | `rebase`
- Optional branch deletion after merge
- 24-hour gate timeout (configurable)

**Arguments**: `pr_number`, `repo`, `--strategy`, `--gate-timeout-hours`, `--no-delete-branch`

---

### `deploy-local-plugin` (v1.0.0)
Deploy local plugin files from the omniclaude repo to the Claude Code plugin cache for immediate testing.

**Key features**:
- **Dry-run by default** — preview all changes before writing
- Automatic version bumping (patch increment)
- Atomic registry updates (no partial writes)
- Repair mode (`--repair-venv`) for `.venv` cache corruption
- Complete source-to-target mapping for all plugin component types

**Arguments**: `--execute`, `--no-version-bump`, `--repair-venv`

---

## 3. Code Review & Pull Requests

### `pr-review`
Comprehensive PR review with strict priority-based organization and merge readiness assessment.

**Key features**:
- Keyword-based classification: `CRITICAL / MAJOR / MINOR / NIT`
- The keyword definitions here are the canonical source used by `local-review` and all other review skills

---

### `pr-review-dev`
PR dev review — fix critical, major, and minor issues found in a PR plus CI failures.

---

### `pr-watch`
Poll a GitHub PR for review feedback. On `CHANGES_REQUESTED`, auto-fix issues and re-request review.

**Used by**: `pr_review_loop` phase in `ticket-pipeline`

---

### `pr-polish`
Full PR readiness loop — resolve merge conflicts, address all review comments and CI failures, then iterate `local-review` until N consecutive clean passes.

---

### `pr-queue-pipeline`
Process a queue of multiple PRs through review and merge in batch order.

---

### `review-cycle`
Guided local code review with human checkpoints and learning mode explanations.

---

### `review-all-prs`
Review all open (non-draft) PRs across OmniNode-ai repos — shows CI status, mergeable state, and groups PRs by readiness.

---

### `list-prs`
Dashboard view of all open PRs across OmniNode-ai repos.

---

### `fix-prs`
Fix issues identified across multiple PRs in batch.

---

### `merge-sweep`
Sweep through a list of PRs and merge those that meet all readiness criteria.

---

## 4. Architecture & Quality

### `defense-in-depth` (v1.0.0)
Use when invalid data causes failures deep in execution. Validates at every layer to make bugs structurally impossible.

**Four validation layers**:
1. **Entry point** — API/service boundary input validation
2. **Business logic** — domain rule enforcement
3. **Environment guards** — context-specific pre-condition checks
4. **Debug instrumentation** — forensic logging for edge cases

---

### `condition-based-waiting` (v1.0.0)
Replace arbitrary `time.sleep()` timeouts with condition polling. Eliminates flaky tests caused by timing guesses.

**Pattern**: Wait for an actual observable condition (e.g., queue empty, file exists, flag set) rather than sleeping for a guessed duration.

**Use when**: Race conditions, timing-dependent tests, inconsistent pass/fail behavior.

---

### `test-driven-development`
Write the test first, watch it fail, then write minimal code to pass. Ensures tests actually verify behavior by requiring a failure first.

**Cycle**: `RED (write failing test) → GREEN (minimal code to pass) → REFACTOR`

---

### `testing-anti-patterns`
Documents and prevents common testing mistakes: testing mock behavior instead of real behavior, polluting production code with test-only methods, and mocking without understanding dependencies.

---

### `ultimate-validate`
Generate and run a comprehensive validation command suite for the current codebase — linting, type-checking, tests, and integration checks — before marking work complete.

---

### `verification-before-completion`
Mandatory check before claiming work is done. Requires running verification commands and confirming output before making any success claims.

**Principle**: Evidence before assertions.

---

## 5. Observability & Diagnostics

### `agent-observability` (v1.0.0)
Real-time monitoring and diagnostics for the OmniClaude agent execution system.

> **Critical**: This skill must be dispatched to `polymorphic-agent` — never run analysis inline.

**Sub-commands**:
- `check-health` — 5-second status snapshot
- `diagnose-errors` — deep error pattern analysis
- `generate-report` — comprehensive metrics report
- `check-agent <agent-id>` — agent-specific performance profiling

---

### `action-logging` (v1.0.0)
Easy-to-use action logging for agents with automatic timing, context management, and Kafka integration.

**Core API** (`ActionLogger` class):
- `log_tool_call()` — log a tool invocation with inputs/outputs
- `log_decision()` — log an agent decision with rationale
- `log_error()` — log an error with context
- `log_success()` — log a successful operation

**Key features**:
- Context manager for automatic timing
- Correlation ID tracking across distributed operations
- Non-blocking async I/O (graceful degradation if Kafka is unavailable)
- Kafka topic: `agent-actions`
- PostgreSQL persistence for long-term storage

---

### `agent-tracking`
Comprehensive tracking suite with five nested sub-skills:

| Sub-Skill | Purpose |
|-----------|---------|
| `log-agent-action` | General agent action logging |
| `log-detection-failure` | Track detection/routing failures |
| `log-performance-metrics` | Performance metric recording |
| `log-routing-decision` | Routing decision audit trail |
| `log-transformation` | Data transformation tracking |

---

### `system-status`
System health monitoring suite with dedicated sub-skills:

| Sub-Skill | Purpose |
|-----------|---------|
| `check-agent-performance` | Agent performance metrics |
| `check-database-health` | DB connection and query health |
| `check-infrastructure` | Service endpoint health |
| `check-kafka-topics` | Event bus topic health |
| `check-pattern-discovery` | Pattern detection status |
| `check-recent-activity` | Recent system activity summary |
| `check-service-status` | Individual service checks |
| `check-system-health` | Comprehensive system check |
| `diagnose-issues` | Root cause analysis for reported issues |
| `generate-status-report` | Full system report output |

---

### `deep-dive` (v1.0.0)
Daily work analysis report combining Linear issues, GitHub PRs, and git commit history.

**Key features**:
- Multiple output modes: display (default), generate (write to file), JSON
- Velocity score (0–100) and effectiveness score (0–100)
- Data sources: Linear MCP, GitHub CLI, git log
- Snapshot creation for canonical data replay
- Custom repository filtering

**Arguments**: `--date`, `--days`, `--save`, `--output`, `--output-dir`, `--json`, `--generate`, `--repos`, `--snapshot-only`, `--no-snapshot`, `--project-id`

---

### `linear-insights`
Daily deep-dive reports and velocity-based project completion estimates using Linear data.

---

### `systematic-debugging`
Four-phase structured debugging framework: root cause investigation → pattern analysis → hypothesis testing → implementation. Ensures understanding before proposing fixes.

**Auto-dispatched by**: `local-review` when a fix attempt fails

---

### `root-cause-tracing`
Trace errors backward through the call stack, adding instrumentation as needed, to identify the original source of invalid data or incorrect behavior.

---

## 6. Planning & Design

### `brainstorming` (v1.0.0)
Refine rough ideas into fully-formed designs through collaborative dialogue before writing code.

**Process**:
1. Understand current context and constraints
2. Ask clarifying questions one at a time
3. Explore 2–3 distinct approaches with trade-offs
4. Present design in digestible sections (200–300 words each)
5. Incremental validation before proceeding

---

### `writing-plans` (v1.0.0)
Create comprehensive implementation plans for engineers with zero codebase context.

**Plan structure per task**:
- Exact file paths to modify or create
- Complete code examples (not pseudocode)
- Step-by-step instructions with expected outputs
- TDD approach — test code appears before implementation code
- Frequent commit points (every 2–5 minutes of work)
- Handoff options: execute inline or save for later

---

### `executing-plans`
Task-by-task plan execution in controlled batches with human review checkpoints between batches.

**Used after**: `writing-plans` to implement a design

---

### `gap-analysis`
Cross-repo integration health audit. Identifies Kafka topic drift, model type mismatches, FK reference drift, API contract drift, and DB boundary violations across repo boundaries.

---

### `gap-fix`
Auto-fix loop for `gap-analysis` findings. Reads a gap-analysis report, classifies findings by auto-dispatch eligibility, dispatches `ticket-pipeline` for safe-only findings, then queues PRs.

---

### `plan-to-tickets`
Convert a structured implementation plan into Linear tickets, one ticket per plan milestone or task group.

---

## 7. State & Recovery

### `checkpoint` (v1.0.0)
*(Also listed under [Workflow Orchestration](#1-workflow-orchestration))*

Pipeline checkpoint management. Write, read, validate, and list phase checkpoints for crash recovery.

---

### `crash-recovery` (v1.0.0)
Show recent pipeline state to orient after an unexpected session end or crash.

**Key features**:
- Reads `~/.claude/pipelines/*/state.yaml` sorted by modification time
- Supports both current and legacy checkpoint schemas
- Detects terminal vs. in-progress phases
- Provides resume suggestions with exact `--resume` commands

**Arguments**: `--count <n>` (default 10), `--in-progress`, `--json`

---

## 8. Ticketing & Linear Integration

### `linear`
Full Linear integration via MCP. Create, update, list, and manage Linear tickets with requirements and definition of done.

---

### `create-ticket` (v1.0.0)
Create a single Linear ticket from arguments, a contract file, or a plan milestone.

**Three mutually-exclusive input sources**:
1. `title` — direct title string
2. `--from-contract <file>` — extract from a ONEX contract YAML
3. `--from-plan <file> --milestone <name>` — extract from a plan document

**Key features**:
- Conflict detection: update / cancel-and-create / skip existing tickets
- Standardized description template
- Architecture dependency validation (use `--allow-arch-violation` to bypass)

**Arguments**: `title`, `--from-contract`, `--from-plan`, `--milestone`, `--repo`, `--parent`, `--blocked-by`, `--project`, `--team`, `--allow-arch-violation`

---

### `create-followup-tickets` (v1.0.0)
Create Linear tickets in batch from code review output (critical/major/minor/nit issues).

**Key features**:
- Reads integrated review output from `local-review` or `pr-review`
- Fuzzy project matching by repo name
- Severity filtering options (e.g., create tickets only for CRITICAL + MAJOR)
- Auto repo labeling from affected files
- Preview mode (`--dry-run`) before committing
- Automatic parent ticket linking

---

### `decompose-epic` (v1.0.0)
*(Also listed under [Workflow Orchestration](#1-workflow-orchestration))*

Analyze a Linear epic and create sub-tickets as children with repo assignments.

---

### `plan-ticket`
Generate a copyable ticket contract template — fill in the blanks and pass to `create-ticket`.

---

### `linear-insights`
Daily deep-dive reports and velocity-based completion estimates using Linear project data.

---

## 9. Supporting Infrastructure

### `using-git-worktrees` (v1.0.0)
Best practices for isolated git worktree development. Use when starting feature work that needs isolation from the current workspace.

**Key pattern**:
```bash
TICKET="OMN-XXXX"
REPO="omniclaude"
git -C /Volumes/PRO-G40/Code/omni_home/$REPO worktree add \
  /Volumes/PRO-G40/Code/omni_worktrees/$TICKET/$REPO \
  -b jonah/$TICKET-description
```

---

### `slack-gate` (v1.0.0)
Post a risk-tiered Slack gate via `chat.postMessage` and poll for human reply using a Bot Token.

**Risk tiers**:
- `LOW_RISK` — informational, no approval required
- `MEDIUM_RISK` — soft gate, reasonable timeout
- `HIGH_RISK` — hard gate, explicit keyword reply required, silence ≠ consent

**Used by**: `epic-team`, `ticket-pipeline`, `ci-fix-pipeline`, `auto-merge`

---

### `requesting-code-review`
Dispatches a `code-reviewer` subagent to review implementation against a plan or requirements before proceeding.

**Use when**: Completing tasks, implementing major features, or before merging to verify work meets requirements.

---

### `receiving-code-review`
Process and respond to incoming code review feedback with technical rigor. Requires verification before implementing suggestions — no performative agreement or blind implementation.

---

### `generate-node`
Generate ONEX nodes via automated code generation with `ContractInferencer` and LLM-powered business logic synthesis.

---

### `setup-statusline`
Configure the Claude Code status line to show folder name, git branch, and PR number.

---

## 10. Advanced & Parallel Execution

### `parallel-solve`
Execute any task in parallel using polymorphic agents with requirements gathering. Use when facing 3+ independent problems that can be investigated without shared state.

---

### `subagent-driven-development`
Dispatch a fresh subagent for each independent task in an implementation plan. Code review runs between tasks as a quality gate, enabling fast iteration.

---

### `dispatching-parallel-agents`
Use when facing 3+ independent failures that can be investigated without shared state. Dispatches multiple Claude agents concurrently and collects findings.

---

### `pipeline-audit`
Systematically audit an end-to-end multi-repo pipeline for integration correctness. Proves every join between services with file-level evidence, dispatches parallel agents per repo and per proof category, and compiles a severity-ordered gap register with actionable tickets.

---

### `rrh` (Release Readiness Handshake)
Opt-in preflight validation pipeline run before any side-effecting phase: A1 (collect) → A2 (validate) → A3 (store).

---

## 11. Shared Libraries & Helpers

All shared helpers live under `skills/_lib/` and `skills/_shared/`:

| Path | Purpose |
|------|---------|
| `_lib/pr-safety/helpers.md` | PR safety validation helpers used by merge skills |
| `_shared/ERROR_HANDLING_FIXES.md` | Common error handling patterns and fixes |
| `_shared/QDRANT_SECURITY.md` | Qdrant security guidance for vector store access |

Skill-specific reference files:
- `action-logging/README.md` + `action-logging/examples/README.md` — full `ActionLogger` API guide
- `generate-node/README.md` — node generation reference
- `testing-skills-with-subagents/examples/CLAUDE_MD_TESTING.md` — skill testing patterns

---

## 12. Architectural Patterns

### Composition Model
Skills compose other skills as "sub-skills" rather than reimplementing logic:

```
epic-team
  └── decompose-epic       (epic → child tickets)
  └── slack-gate           (human approval gates)
  └── ticket-pipeline      (per-ticket execution)
        └── ticket-work    (implementation phase)
        └── local-review   (review + fix loop)
        └── ci-watch       (CI monitoring)
              └── ci-fix-pipeline  (auto-fix CI)
                    └── ci-failures  (failure analysis)
        └── pr-watch       (PR review monitoring)
        └── auto-merge     (merge with gate)
        └── checkpoint     (state persistence)
```

### Dispatch Pattern
Heavy computation dispatches to `Task(subagent_type="onex:polymorphic-agent")` with a detailed prompt. The calling skill handles:
- State persistence and phase transitions
- Slack notifications
- Git operations (commit, push)
- Result aggregation

### Result Communication
Sub-skills write `ModelSkillResult` JSON to `~/.claude/skill-results/{context_id}/` for parent orchestrators to read without tight coupling.

### Policy-Driven Automation
All auto-advance decisions are governed by explicit policy switches — `auto_advance: true/false`, `max_iterations: N`, `fix_all: true/false`. Agent judgment is used for analysis; policy switches control the automation boundary.

### State Persistence
Long-running pipelines write YAML state files:
- **Pipelines**: `~/.claude/pipelines/{ticket_id}/state.yaml`
- **Epics**: `~/.claude/epics/{epic_id}/state.yaml`
- **Checkpoints**: `~/.claude/checkpoints/{ticket_id}/{run_id}/phase_{N}_{name}_a{attempt}.yaml`
- **Review notes**: `~/.claude/review-notes/{session_id}/`
- **Skill results**: `~/.claude/skill-results/{context_id}/`

---

## Quick Reference by Use Case

| What you want to do | Skill to use |
|---------------------|-------------|
| Work a Linear ticket end-to-end | `ticket-pipeline` |
| Work an entire epic autonomously | `epic-team` |
| Review code before committing | `local-review` |
| Fix CI failures | `ci-watch` or `ci-fix-pipeline` |
| Merge a PR safely | `auto-merge` |
| Design a new feature | `brainstorming` → `writing-plans` |
| Create tickets from a plan | `plan-to-tickets` |
| Debug a failing test | `systematic-debugging` |
| Check system health | `system-status` |
| Recover from a crash | `crash-recovery` |
| Deploy plugin changes locally | `deploy-local-plugin` |
| Create follow-up tickets from review | `create-followup-tickets` |
| Analyze daily work output | `deep-dive` |
