# Core Worktree Convention

This convention standardizes how to use Git worktrees when only the core lane is active. The goal is to keep `main` stable while all feature work happens on `core`.

## Branch Model

- Stable branch: `main`
- Working branch: `core`

All core changes are committed on `core` and merged back to `main` through PRs.

## Worktree Location and Naming

- Primary location: `.worktrees/` at repo root.
- Worktree directory for core: `.worktrees/core-bootstrap`
- Branch used in this worktree: `core`

Use additional core worktrees only for temporary experiments, and remove them after merge.

## One-Time Setup

1. Ensure `.worktrees/` is ignored in `.gitignore`.
2. From repo root, create your core worktree:
   - `git worktree add .worktrees/core-bootstrap -b core`
3. Enter worktree and install deps:
   - `python3.12 -m venv .venv`
   - `source .venv/bin/activate`
   - `pip install -e ".[dev]"`
4. Run baseline checks before coding:
   - `ruff check src/ tests/ .cursor/hooks/`
   - `pytest tests/ -v`

If baseline is not green, stop and post failures in team chat before feature commits.

## Daily Workflow

1. Start in your core worktree and sync:
   - `git fetch origin`
   - `git rebase origin/main` (while on `core`)
2. Keep commits scoped to one task or fix.
3. Push `core` frequently:
   - `git push`
4. Open PRs from `core` into `main`.
5. Re-run lint and tests before each push.

## Scope Ownership

`core` owns all active work in this setup, including:

- `src/omnicursor/`
- `.cursor/rules/`
- `.cursor/hooks/`
- repo docs and tests required for the core changes

## Pull Request Expectations

- PR title format: `[core] <short outcome>`
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
3. Keep `core` (do not delete it)
4. If temporary extra worktrees were created, remove them:
   - `git worktree remove .worktrees/<temp-core-worktree>`
5. `git worktree prune`

Run cleanup at least once per week to avoid stale worktrees.
