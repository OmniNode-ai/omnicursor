# Architecture Reasoning — Prepared Answers

---

## Q1: Why separate rules, hooks, and skills instead of one big prompt?

They have different **reliability, timing, and ownership**:

- **Rules** are always loaded by Cursor at session start — no prompt needed, no model decision required. They inject static background knowledge (OmniNode vocabulary, conventions, skill paths). They're reliable because Cursor enforces them.
- **Hooks** run deterministically in Python before the model sees anything. They don't depend on the model making the right decision — they fire on lifecycle events (prompt submitted, file saved, shell command). They can block, warn, or inject context unconditionally.
- **Skills** are long-form methodology loaded on demand from disk. They're too long to live in a rule (Cursor has context limits) and they need an LLM to read and apply them. Loading them at prompt time keeps context lean.

One big prompt would be brittle: it couldn't block a shell command, couldn't fire on file save, and would force the model to parse 50 pages of methodology every time.

---

## Q2: What happens if Cursor drops hook support in a future release?

The system degrades gracefully in layers:

- **Rules + skills still work** — the model still has OmniNode vocabulary and can read skill files when asked.
- **Automatic routing is lost** — the model no longer gets pre-prompt agent selection. Routing would need to become prompt-driven ("you are a debugging agent") or move into a rule with keyword detection.
- **Shell guard and edit-time lint disappear** — no Python runs before shell execution or after file edits. Those guardrails would need to be reimplemented as CI checks or pre-commit hooks.
- **Pattern injection stops** — learned patterns would need to be injected via a rule that reads `learned_patterns.json` on startup.

The architecture is layered specifically so each layer can exist independently. Losing hooks hurts automation but doesn't break the methodology.

---

## Q3: Why is the routing confidence floor 0.55 and not 0.80?

It's a tunable trade-off between two failure modes:

- **Too high (0.80+):** Too many false negatives — prompts that should route to a specialized agent fall through to the generic fallback. The system feels unhelpful; users get generic responses when a specialized agent would have been better.
- **Too low (0.30-):** Too many false positives — prompts get routed to the wrong specialized agent, injecting irrelevant context and confusing the model.

0.55 was chosen as the point where fuzzy keyword matches (0.55–0.75) are decisive enough to be useful, while exact trigger matches (0.95) are always correct. The number matters less than understanding that it's a tunable parameter — in production you'd evaluate routing accuracy on a labeled prompt set and adjust accordingly.

---

## Q4: Why does omniclaude have 80+ skills but OmniCursor ships far fewer?

Deliberate scope, not running out of time.

OmniClaude's skills include many that are infrastructure-bound: `merge-sweep` requires GitHub MCP and org-level write access, `autopilot` requires headless `claude -p` execution, `golden-chain-sweep` requires a running Kafka cluster. Porting those to Cursor would either be fake (pretend the skill works without the infrastructure) or require rebuilding the infrastructure, which defeats the purpose of a lightweight plugin.

OmniCursor's strategy was foundation-first: build the hooks, routing, compliance system, and a curated set of pure-methodology skills that work without Kafka, org integrations, or ONEX runtime. The 16 skills cover the core development workflow (debug, plan, review, implement, execute). Skills get added when a workflow needs them, not to match a count.

---

## Q5: What would you build next if you had another semester?

Three things in order of impact:

1. **Pattern lifecycle with real feedback loop** — right now patterns are written from session outcomes but there's no evaluation of whether injecting a pattern actually improved results. A real system would track: "did sessions where pattern X was injected end in success more often than sessions without it?" and adjust weights accordingly. This requires logging injection outcomes, not just injection events.

2. **Routing accuracy evaluation loop** — the three-strategy scoring works but has never been evaluated against a labeled prompt set. Building a small evaluation harness (100 labeled prompts, expected agent, measure precision/recall per agent) would let you tune `HARD_FLOOR`, adjust trigger phrases, and identify which agents are under- or over-triggering.

3. **Multi-agent coordination** — right now `execute_plan` implements tickets serially in one session. A real orchestrator would spawn parallel agents per ticket (using Claude Code's `Agent` tool or subagent spawning), coordinate via shared state, and handle dependencies between parallel workstreams. This is what OmniClaude's `epic-team` skill does and it's the biggest capability gap.

---

## Q6: Why are skills markdown files and not Python functions?

Because the LLM is the runtime.

A Python function executes logic — it takes inputs, runs code, returns outputs. If you want to add a new step, you write more code and redeploy.

A skill file shapes reasoning — it tells the LLM *how to think* about a problem: what questions to ask, what order to follow, what anti-patterns to avoid. The LLM reads it and applies the methodology to the specific situation. You can update the methodology by editing a Markdown file, no deployment required.

The alternative — encoding debugging methodology as Python code — would produce a rigid, brittle decision tree that couldn't handle the variety of real debugging situations. The LLM's ability to interpret and apply natural language instructions is the whole point.

---

## Q7: Which skill would NOT port well from omniclaude?

**`merge-sweep`** — requires GitHub MCP with org-level write access (to merge PRs across multiple repos), a Linear MCP to update ticket states, and knowledge of which repos are in the merge queue. None of that infrastructure exists in a simple Cursor project.

**`autopilot`** — requires headless `claude -p` execution, a running Kafka event bus for dispatching subtasks, and the full ONEX contract system for routing work to the right nodes. It's not a methodology skill — it's an infrastructure orchestrator.

**`golden-chain-sweep`** — validates Kafka-to-DB data pipelines end-to-end. Completely meaningless without a running Kafka cluster and PostgreSQL database.

The pattern: skills that are pure methodology (debug, plan, review, brainstorm) port well. Skills that are infrastructure orchestration (merge, deploy, sweep, autopilot) don't — they're not methodology documents, they're thin wrappers around external systems.
