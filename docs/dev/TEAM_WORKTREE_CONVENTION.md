# Team Worktree Convention (4-Member)

This convention standardizes how the OmniCursor team uses Git worktrees and GitHub branches to avoid conflicts and keep PRs reviewable.

## Team Roles and Branch Prefixes

Use one prefix per role. Every branch and worktree name must start with that prefix.

- Member 1 - CI and quality automation: `ci/`
- Member 2 - OmniCursor repo core (library + Cursor surface): `core/`
- Member 3 - OmniClaude reuse and pattern lifecycle: `reuse/`
- Member 4 - External ecosystem integration: `integration/`

Examples:

- `ci/add-pr-workflow`
- `core/harden-agent-routing`
- `reuse/store-pattern-mvp`
- `integration/omniintelligence-bridge-poc`

## Worktree Location and Naming

- Primary location: `.worktrees/` at repo root.
- Worktree directory name must match branch slug without `/`.
- Format: `.worktrees/<prefix>-<short-topic>`

Examples:

- Branch: `core/harden-agent-routing`
- Worktree: `.worktrees/core-harden-agent-routing`

## One-Time Setup

1. Ensure `.worktrees/` is ignored in `.gitignore`.
2. From repo root, create your worktree:
   - `git worktree add .worktrees/<prefix>-<topic> -b <prefix>/<topic>`
3. Enter worktree and install deps:
   - `python3.12 -m venv .venv`
   - `source .venv/bin/activate`
   - `pip install -e ".[dev]"`
4. Run baseline checks before coding:
   - `ruff check src/ tests/ .cursor/hooks/`
   - `pytest tests/ -v`

If baseline is not green, stop and post failures in team chat before feature commits.

## Daily Team Workflow

1. Start in your assigned worktree and sync:
   - `git fetch origin`
   - `git rebase origin/main`
2. Keep commits scoped to one task or fix.
3. Open a PR from your role-prefixed branch.
4. Link related PRs when cross-role changes are required.
5. Re-run lint and tests before each push.

## Ownership Boundaries

- `ci/*` owns `.github/workflows/`, quality gates, and baseline automation.
- `core/*` owns `src/omnicursor/`, `.cursor/rules/`, and `.cursor/hooks/` behavior in this repo.
- `reuse/*` owns reusable OmniClaude-derived patterns, routing borrow logic, and pattern write-path implementation.
- `integration/*` owns OmniCursor bridges to OmniIntelligence, OmniMemory, OmniDash, and local integration orchestration.

When work crosses boundaries, one role is the primary owner and others contribute via small follow-up PRs.

## Merge and Conflict Policy

- Merge order for cross-cutting work:
  1. `ci/*` baseline and guardrails
  2. `core/*` internal behavior changes
  3. `reuse/*` borrowed logic and pattern path updates
  4. `integration/*` external bridge updates
- Never force-push shared branches.
- Prefer rebasing your branch on `origin/main` before requesting review.
- If two branches touch the same file heavily, pair for a conflict-resolution session before merge.

## Pull Request Expectations

- PR title format: `[<role>] <short outcome>`
  - Example: `[core] tighten agent context fallback behavior`
- Include:
  - Why the change is needed
  - Scope and risk
  - Test evidence (`ruff` and `pytest`)
  - Follow-up items for other roles, if any

## Worktree Cleanup

After PR merge:

1. `git checkout main`
2. `git pull --ff-only`
3. `git branch -d <prefix>/<topic>`
4. `git worktree remove .worktrees/<prefix>-<topic>`
5. `git worktree prune`

Run cleanup at least once per week to avoid stale worktrees.
