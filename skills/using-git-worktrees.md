---
name: "onex-using-git-worktrees"
description: >-
  Use this skill when starting feature work that needs isolation from the current workspace, or when you need to work on multiple branches simultaneously. The goal is to create an isolated worktree with a verified clean baseline.
disable-model-invocation: true
---

# onex-using-git-worktrees

Use this skill when starting feature work that needs isolation from the current workspace, or when you need to work on multiple branches simultaneously. The goal is to create an isolated worktree with a verified clean baseline.

## Purpose

Git worktrees create isolated workspaces sharing the same repository, allowing work on multiple branches without switching. This skill ensures worktrees are created safely with proper directory selection, .gitignore verification, and baseline test confirmation.

## Prerequisites

- A git repository
- A branch name for the new worktree

## Workflow

1. **Select the worktree directory.**
   Follow this priority order:
   - Check if `.worktrees/` or `worktrees/` already exists. If both exist, prefer `.worktrees/`.
   - Check CLAUDE.md or project docs for a stated preference.
   - If neither exists, ask the user: `.worktrees/` (project-local, hidden) or a global location like `~/.config/worktrees/<project>/`.

2. **Verify .gitignore for project-local directories.**
   If using a project-local directory (`.worktrees/` or `worktrees/`), check that the directory pattern is in `.gitignore`. If it is not, add it and commit the change before creating the worktree. This prevents accidentally committing worktree contents.

3. **Create the worktree.**
   Run `git worktree add <path> -b <branch-name>`. After creation, install project dependencies by detecting the project type (package.json, pyproject.toml, requirements.txt, Cargo.toml, go.mod) and running the appropriate install command.

4. **Verify a clean baseline.**
   Run the project's test suite in the new worktree. If tests pass, the worktree is ready. If tests fail, report the failures and ask whether to proceed or investigate — do not silently continue with a broken baseline.

5. **Report the worktree location.**
   Output the full path to the worktree, test results summary, and confirmation that the workspace is ready.

## Expected Output Format

A status report containing:
- Worktree path (absolute)
- Branch name
- Dependency installation result
- Test results (count, pass/fail)
- Ready/not-ready verdict

## Quality Checklist

- [ ] Directory selected following the priority order (existing > docs > ask)
- [ ] .gitignore verified before creating a project-local worktree
- [ ] Dependencies installed based on project type detection
- [ ] Baseline tests run and results reported
- [ ] Worktree path and readiness status communicated clearly
