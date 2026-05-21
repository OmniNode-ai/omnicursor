# Architecture — OmniCursor + starter-pack invariants

This file serves **two roles**:

1. **OmniCursor product shape (current repo)** — how the IDE integration is structured.
2. **Starter-pack / capstone invariants** — the 3-bucket model, frozen HTTP adapter contract, repo detection, and handoff rules below. Those sections are still authoritative for rubric conformance where applicable.

## OmniCursor runtime (summary)

| Layer | Location | Role |
|--------|-----------|------|
| **Rules** | `.cursor/rules/*.mdc` | Behavior and methodology; model reads `skills/*.md` by path. |
| **Hooks** | `.cursor/hooks.json`, `.cursor/hooks/scripts/*.py` | Deterministic lifecycle (prompt routing hint, shell guard, edit lint signal, session outcome). Hook code is **stdlib only** and does not import `omnicursor`. |
| **Skills** | `skills/*.md` + `.cursor/skills/onex-*/SKILL.md` | Methodology documents on disk (canonical ids: `onex-<slug>`). |
| **Library** | `src/omnicursor/` | `agents`, `skills` loader, `compliance`, `node_contracts` — for **tests, CI, and optional scripting**; optional integration with the wider OmniNode stack via HTTP/subprocess/Kafka is described in [`dev/OMNICURSOR_SYSTEM_DESIGN.md`](./dev/OMNICURSOR_SYSTEM_DESIGN.md). |

Optional integrations (e.g. Linear) use Cursor’s MCP and rules as documented in the repo. Deeper developer notes: [`dev/README.md`](./dev/README.md), [`../CLAUDE.md`](../CLAUDE.md).

---

## 3-Bucket Classification (starter-pack invariants)

### Classification Rule (one sentence per bucket)

| Bucket | Classification Rule |
|--------|-------------------|
| **Bucket 1** | No external service call required; may write local files as output but does not read external state to function. |
| **Bucket 2** | Reads bounded local files or cwd context to produce output; does not require any external service. |
| **Bucket 3** | Requires at least one external service call (Linear MCP, Kafka, or Python validator with omnibase_core importable). |

### Skill Classification Table

| Skill | Bucket | External Deps | Notes |
|-------|--------|---------------|-------|
| `brainstorming` | 1 | none | Writing to `docs/plans/` is output, not a dependency |
| `writing-plans` | 1 | none | Writing to `docs/plans/` is output, not a dependency |
| `plan-ticket` | 2 | reads cwd, README.md, dir listing | Bridge exercise; no mandatory service |
| `decompose-epic` | 3 | Linear MCP (mandatory) | Stage 2 only |
| `generate-ticket-contract` | 3 | Linear MCP + Python validator | Stage 2 only |
| `linear` | 3 | Linear MCP | Stage 2 only |
| `executing-plans` | 3 | Linear MCP + Kafka routing | Stage 2 only |

### Per-Bucket Entry/Exit Criteria

**Bucket 1 — Entry:** User provides idea or design intent. No files required.
**Bucket 1 — Exit:** Design doc written to `docs/plans/YYYY-MM-DD-*-design.md`. Handoff line references the path.

**Bucket 2 — Entry:** User provides task description. README.md (or equivalent) available in cwd.
**Bucket 2 — Exit:** YAML ticket template output to stdout. Repo detected via 3-priority chain.

**Bucket 3 — Entry:** External service configured and reachable. dry_run returns `status: "ok"`.
**Bucket 3 — Exit:** Adapter response `stdout` displayed verbatim. Artifacts listed. Next actions offered.

---

## Frozen Adapter Contract

**All Bucket 3 rules call this endpoint.** The contract is frozen — students implement against it, not around it. Changes to this contract require a new version.

### Request

```
POST /onex/api/v1/skills/{skill_name}
Content-Type: application/json
```

**Body fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `skill_name` | string | yes | Path param OR body field — same value |
| `input` | object | yes | Skill-specific schema (see per-skill section below) |
| `dry_run` | boolean | yes | Always `true` on first call |
| `context.repo` | string | yes | One of the 7 valid repo names |
| `context.cwd` | string | yes | Relative path from starter pack root — **NOT** an absolute path |
| `context.user_id` | string | no | Optional identifier |

**Rules:**
- `dry_run: true` is MANDATORY on the first call. Never send `dry_run: false` as the first call.
- `context.cwd` must be a relative path. Absolute paths (starting with `/`) are rejected.
- If dry_run returns `status: "blocked"` or `"error"`: do NOT attempt a live call.

### Response

**Success (`status: "ok"`):**

| Field | Type | Description |
|-------|------|-------------|
| `status` | `"ok"` | Request succeeded |
| `stdout` | string | Display to user verbatim |
| `artifacts` | array | Files written (may be empty) |
| `artifacts[].type` | `"plan" \| "contract" \| "ticket" \| "doc"` | Artifact category |
| `artifacts[].path` | string | Relative path to the file |
| `artifacts[].description` | string | Human-readable description |
| `next_actions` | array | Optional follow-on skill suggestions |
| `error` | ABSENT | Not present when status is `"ok"` |

**Error/Blocked (`status: "error"` or `"blocked"`):**

| Field | Type | Description |
|-------|------|-------------|
| `status` | `"error" \| "blocked"` | Request failed or was blocked |
| `stdout` | string | May be empty or partial |
| `error` | object | PRESENT — describes the failure |
| `error.code` | string | See error codes table below |
| `error.message` | string | Human-readable explanation |

### Error Codes

| Code | Meaning | Rule Behavior |
|------|---------|---------------|
| `VALIDATION_ERROR` | Input schema invalid | Fix input, retry once |
| `LINEAR_UNAVAILABLE` | Linear MCP not reachable | Fail-soft, complete manually |
| `BLOCKED` | dry_run policy blocked the operation | Do not attempt live call |
| `TIMEOUT` | Service did not respond within 10s | Fail-soft, complete manually |

### Timeout and Fail-Soft Definition

**Timeout:** 10 seconds. If no response within 10s, treat as `TIMEOUT` error.

**Fail-soft behavior:**
- Rule outputs: `"Service unavailable. Complete manually: [next step description]"`
- Rule does NOT retry automatically
- Rule does NOT loop or re-invoke the endpoint
- Rule does NOT pretend the operation succeeded

### dry_run Semantics (Critical)

- One dry_run call per user invocation — never repeated
- If dry_run returns `status: "blocked"` or `"error"`: do NOT attempt live call
- If dry_run returns `status: "ok"`: rule may proceed with `dry_run: false`
- `dry_run: true` and `dry_run: false` calls count as separate invocations for billing/rate-limit purposes

### Per-Skill Input Schemas

**decompose-epic:**
```json
{
  "epic_id": "OMN-XXXX",
  "dry_run": true,
  "repos": []
}
```

**linear (create ticket):**
```json
{
  "title": "string",
  "description": "string",
  "repo": "omniclaude",
  "team": "string"
}
```

**generate-ticket-contract:**
```json
{
  "ticket_id": "OMN-XXXX",
  "title": "string",
  "description": "string",
  "repo": "omniclaude"
}
```

---

## Deterministic Repo Detection Algorithm

This is the reference implementation for rule `12-plan-ticket.mdc`. Student implementations must follow this algorithm exactly — variations that produce different results for the same input are non-conformant.

```
function detect_repo(cwd_path, prompt_text, readme_content):
  VALID_REPOS = ["omniclaude", "omnibase_core", "omnibase_infra", "omnidash",
                 "omniintelligence", "omnimemory", "omninode_infra"]

  // Priority 1: CWD or prompt
  combined = (cwd_path + " " + prompt_text).lower()
  for repo in VALID_REPOS:
    if repo in combined:
      return repo

  // Priority 2: README project name
  readme_lower = readme_content.lower()
  for repo in VALID_REPOS:
    if repo in readme_lower:
      return repo

  // Priority 3: Ask user
  return ASK_USER(choices=VALID_REPOS + ["other"])
```

**Conformance check:** Given identical `(cwd_path, prompt_text, readme_content)` inputs, two conformant implementations must return the same repo name. If they differ, at least one is non-conformant.

---

## Handoff Protocol

Each rule ends with a handoff line that references the saved artifact path — not "paste above."

**Format:**
```
**Next step**: In Cursor Composer, invoke rule `<rule-name>` and provide the path `<artifact-path>` as context.
```

The rule fills in the actual date and topic when it writes the file. Students must use the exact artifact path in their handoff line.

**Non-conformant examples (rubric FAIL):**
- "Paste the above design into the next rule"
- "Use the writing-plans rule with the design above"
- "Copy the output and run writing-plans"

**Conformant examples (rubric PASS):**
- `**Next step**: In Cursor Composer, invoke rule \`11-writing-plans\` and provide the path \`docs/plans/2026-03-01-webhook-retry-design.md\` as context.`
