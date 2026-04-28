from omnicursor.compliance import check_compliance, COMPLIANCE_REGISTRY


def test_systematic_debugging_fully_compliant() -> None:
    summary = (
        "The symptom was a TypeError exception in the parser. "
        "The hypothesis is that the input validator rejects None values. "
        "The fix changes the validator to handle None. "
        "Verification: run pytest to confirm the test passes."
    )
    result = check_compliance("systematic-debugging", summary)
    assert result.skill_name == "systematic-debugging"
    assert result.compliant is True
    assert result.missing == []
    assert all(result.checks.values())


def test_systematic_debugging_missing_fix() -> None:
    summary = (
        "The symptom was a timeout error. "
        "The root cause is a missing retry in the HTTP client. "
        "Verification: run the test suite to confirm."
    )
    result = check_compliance("systematic-debugging", summary)
    assert result.compliant is False
    assert "suggests_minimal_fix" in result.missing
    assert result.checks["states_problem_clearly"] is True
    assert result.checks["provides_hypothesis"] is True
    assert result.checks["suggests_minimal_fix"] is False
    assert result.checks["includes_verification_step"] is True


def test_brainstorming_fully_compliant() -> None:
    summary = (
        "Which approach do you prefer? Option A uses a REST API, "
        "Option B uses GraphQL. The trade-off is simplicity vs flexibility. "
        "I recommend Option A because it fits the existing architecture. "
        "The design covers component structure and data flow. "
        "Saved to docs/plans/2026-03-28-webhook-design.md."
    )
    result = check_compliance("brainstorming", summary)
    assert result.skill_name == "brainstorming"
    assert result.compliant is True
    assert result.missing == []


def test_brainstorming_missing_approaches() -> None:
    summary = (
        "Here is the design for the webhook feature. "
        "The architecture uses a REST endpoint. "
        "Saved to docs/plans/2026-03-28-webhook-design.md."
    )
    result = check_compliance("brainstorming", summary)
    assert result.compliant is False
    assert "presents_multiple_approaches" in result.missing


def test_unknown_skill_returns_no_registry() -> None:
    result = check_compliance("nonexistent-skill", "some summary")
    assert result.compliant is False
    assert "no_registry_entry_for_nonexistent-skill" in result.missing
    assert result.checks == {}


def test_all_skills_have_registry_entries() -> None:
    expected = {
        "systematic-debugging",
        "brainstorming",
        "writing-plans",
        "plan-ticket",
        "pr-review",
        "pr-polish",
        "hostile-reviewer",
        "defense-in-depth",
        "merge-planner",
        "insights-to-plan",
        "handoff",
        "using-git-worktrees",
        "recap",
        "plan-review",
        "plan-to-tickets",
        "execute-plan",
    }
    assert set(COMPLIANCE_REGISTRY.keys()) == expected


def test_writing_plans_compliance() -> None:
    summary = (
        "Implementation plan. Goal: add webhook support. "
        "Architecture: REST API with queue. Tech stack: Python, FastAPI. "
        "Phase 1: Step 1: Write the failing test in tests/test_webhook.py. "
        "Step 2: Run test to confirm fail. Step 3: Implement src/webhook.py. "
        "Commit: git add && git commit. "
        "Adversarial review: R1 count integrity checked, R2 acceptance criteria checked."
    )
    result = check_compliance("writing-plans", summary)
    assert result.compliant is True


def test_plan_ticket_compliance() -> None:
    summary = (
        "Detected repo: omniclaude. "
        "Generated YAML template with title: 'Add webhook endpoint'. "
        "Requirements section with R1 statement and acceptance criteria. "
        "Verification: pytest and ruff lint checks. Blocking: true. "
        "Created Linear ticket via tracker.create_issue. Ticket url: linear.app/..."
    )
    result = check_compliance("plan-ticket", summary)
    assert result.compliant is True


def test_hostile_reviewer_fully_compliant() -> None:
    summary = (
        "Adversarial review using skeptical analytical stance. "
        "Findings classified by severity: CRITICAL (1), MAJOR (2), MINOR (1), NIT (3). "
        "Evidence: file src/auth.py line 42 — missing retry guard. Impact: data loss. "
        "Fix: add retry with exponential backoff. What to change: wrap call in retry loop. "
        "Iterating to convergence: 3 consecutive clean passes. "
        "Final verdict: risks_noted. Stable after pass 4."
    )
    result = check_compliance("hostile-reviewer", summary)
    assert result.skill_name == "hostile-reviewer"
    assert result.compliant is True
    assert result.missing == []
    assert all(result.checks.values())


def test_hostile_reviewer_missing_adversarial_stance() -> None:
    summary = (
        "Findings classified by severity: CRITICAL, MAJOR, MINOR. "
        "Evidence shows file src/auth.py has an issue. Fix: update the code. "
        "Pass 1 was clean, pass 2 was clean. Verdict: clean."
    )
    result = check_compliance("hostile-reviewer", summary)
    assert result.compliant is False
    assert "uses_adversarial_stance" in result.missing


def test_hostile_reviewer_missing_convergence() -> None:
    summary = (
        "Adversarial skeptical review. "
        "Findings: CRITICAL defect in auth layer. Evidence: file auth.py. "
        "Fix: rewrite the method. What to change: see line 12. "
        "Final verdict: blocking_issue."
    )
    result = check_compliance("hostile-reviewer", summary)
    assert result.compliant is False
    assert "iterates_to_convergence" in result.missing


def test_hostile_reviewer_missing_verdict() -> None:
    summary = (
        "Adversarial skeptical review with hidden defects assumed. "
        "Findings classified: CRITICAL severity issue found. "
        "Evidence: file db.py, impact high. Fix: add validation. "
        "Convergence achieved after 3 iterations."
    )
    result = check_compliance("hostile-reviewer", summary)
    assert result.compliant is False
    assert "states_verdict" in result.missing


def test_recap_fully_compliant() -> None:
    summary = (
        "Session outcome was success. "
        "Files edited: src/foo.py, src/bar.py. "
        "Suggested next steps: continue the refactor."
    )
    result = check_compliance("recap", summary)
    assert result.compliant is True
    assert result.missing == []


def test_recap_missing_next_steps() -> None:
    summary = (
        "Session outcome was success. "
        "Files edited: src/foo.py."
    )
    result = check_compliance("recap", summary)
    assert result.compliant is False
    assert "suggests_next_steps" in result.missing


def test_plan_review_fully_compliant() -> None:
    summary = (
        "Checking plan file docs/plans/my-plan.md. "
        "Count integrity: 5 tasks found, prose says 5. Pass. "
        "Acceptance criteria: all criteria are testable. Pass. "
        "Verdict: PASS — no critical or major findings."
    )
    result = check_compliance("plan-review", summary)
    assert result.compliant is True
    assert result.missing == []


def test_plan_review_missing_verdict() -> None:
    summary = (
        "Checking count integrity and acceptance criteria. "
        "Found 3 tasks. Criteria look testable."
    )
    result = check_compliance("plan-review", summary)
    assert result.compliant is False
    assert "states_verdict" in result.missing


def test_plan_to_tickets_fully_compliant() -> None:
    summary = (
        "Parsing plan file docs/plans/my-plan.md. "
        "Found 5 task sections (## Task N: headings). "
        "Created Linear epic: OMN-100. "
        "Created tickets: OMN-101, OMN-102, OMN-103, OMN-104, OMN-105. "
        "Ticket IDs returned to caller."
    )
    result = check_compliance("plan-to-tickets", summary)
    assert result.compliant is True
    assert result.missing == []


def test_plan_to_tickets_missing_epic() -> None:
    summary = (
        "Parsing plan file. Found 3 tasks. "
        "Created tickets: OMN-1, OMN-2, OMN-3."
    )
    result = check_compliance("plan-to-tickets", summary)
    assert result.compliant is False
    assert "creates_epic" in result.missing


def test_execute_plan_fully_compliant() -> None:
    summary = (
        "Running execute_plan on docs/plans/my-plan.md. "
        "plan-review: PASS. "
        "plan-to-tickets: created 3 tickets (OMN-101, OMN-102, OMN-103). "
        "Implemented ticket OMN-101: passed. "
        "Implemented ticket OMN-102: passed. "
        "Implemented ticket OMN-103: blocked after 2 fix attempts. "
        "Summary: 2 passed, 1 blocked, 0 skipped."
    )
    result = check_compliance("execute-plan", summary)
    assert result.compliant is True
    assert result.missing == []


def test_execute_plan_missing_summary() -> None:
    summary = (
        "Running plan-review: PASS. "
        "Created tickets via plan-to-tickets."
    )
    result = check_compliance("execute-plan", summary)
    assert result.compliant is False
    assert "reports_summary" in result.missing

