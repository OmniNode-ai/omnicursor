# Student Guide — OmniNode Cursor Starter Pack

Welcome to the OmniNode Capstone Cursor Starter Pack. This guide walks you through 6 phases
of progressively increasing complexity, from reading existing skills to implementing and testing
the methodology pipeline through ticket templates.

---

## Access Requirements

**Stage 1 (Phases 1–5):** Requires only the public `omniclaude` repository.
- Clone: `git clone https://github.com/OmniNode-ai/omniclaude.git`
- No OmniNode infrastructure, Linear, Kafka, or Python runtime required

**Bucket 3 (read-only in this pack):** See `docs/ARCHITECTURE.md` for the frozen contract narrative. This OmniCursor tree does **not** ship a Cursor rule or `adapter-stub` skill — capstone demos stop at YAML ticket templates + manual tracker steps unless your course adds integration separately.

---

## 5-Phase Plan

| Phase | What | Artifacts | Pass Criteria |
|-------|------|-----------|---------------|
| **1 Read** | Clone omniclaude (public repo). Read 3 SKILL.md files using rules `00-omninode-concepts` and `01-codebase-research`. | Written summary doc | Correctly identifies invariants + bucket classification for each of the 3 skills |
| **2 Translate brainstorming** | Port `brainstorming/SKILL.md` → `10-brainstorming.mdc` | Rule file + Cursor session transcript | Passes brainstorming rubric with all 3 test prompts |
| **3 Full methodology pipeline** | Port `writing-plans/SKILL.md` → `11-writing-plans.mdc` and `plan-ticket/SKILL.md` → `12-plan-ticket.mdc` | 3 rule files chained | Chain passes: idea → design file → plan file → ticket template |
| **4 Integration gap** | Attempt porting `decompose-epic/SKILL.md`. Document what breaks. Write `adapter-interface.md` | `adapter-interface.md` doc | Correctly identifies all Bucket 3 deps; defines input schema for adapter |
| **5 Demo** | Live Cursor session: brainstorm → plan → ticket template in one chain | `cursor-omninode.zip` | Full chain in one session; brainstorming, writing-plans, and plan-ticket rubrics pass |

---

## Phase 1: Read and Classify

### What to do

1. Clone the public omniclaude repo:
   ```
   git clone https://github.com/OmniNode-ai/omniclaude.git
   ```

2. Open `cursor-omninode/` in Cursor (this starter pack — not the cloned repo)

3. Use rule `00-omninode-concepts` (always active) and `01-codebase-research` (always active) to read:
   - `omniclaude/plugins/onex/skills/brainstorming/SKILL.md`
   - `omniclaude/plugins/onex/skills/writing-plans/SKILL.md`
   - `omniclaude/plugins/onex/skills/plan-ticket/SKILL.md`

4. Write a summary doc at `docs/plans/phase-1-skill-analysis.md` with:
   - For each skill: the bucket classification and rationale
   - The key invariants extracted from each SKILL.md
   - What external dependencies (if any) would prevent a direct Cursor port

### Pass Criteria

- [ ] Correctly classifies all 3 skills by bucket (brainstorming=1, writing-plans=1, plan-ticket=2)
- [ ] Identifies "one question per message" as a key brainstorming invariant
- [ ] Identifies the adversarial review R1/R2 as key writing-plans invariants
- [ ] Identifies repo detection as the key plan-ticket complexity
- [ ] Notes that plan-ticket reads README.md but has no mandatory external service call

---

## Phase 2: Translate Brainstorming

### Pass/Fail Detail

**PASS** requires all 7 criteria:

- [ ] Rule activates within the first response (auto based on description keywords OR via `@10-brainstorming` mention)
- [ ] Rule announces what it read before using file content (bounded research announcement)
- [ ] Every question-containing message has exactly ONE question
- [ ] At least 2 approaches with named trade-offs before settling on design
- [ ] Design sections are 200–300 words each with a check-in after each section
- [ ] Final message contains the literal handoff line with the actual artifact path
- [ ] Design file exists at `docs/plans/YYYY-MM-DD-<topic>-design.md` after session

**FAIL** (any one causes fail):

- Two or more questions in a single message
- No approach comparison before settling on design
- Handoff line says "paste above" instead of naming the file path
- Design file not written to disk

### Test Prompts to Run

1. `tests/prompts/brainstorming/01-simple-api.md` — baseline
2. `tests/prompts/brainstorming/02-refactor.md` — YAGNI stress test
3. `tests/prompts/brainstorming/03-ambiguous-idea.md` — one-question stress test

All 3 must pass the rubric in `tests/rubrics/brainstorming.md`.

---

## Phase 3: Full Methodology Pipeline

Port `writing-plans` and `plan-ticket` rules. Then run the full chain:

1. Use `@10-brainstorming` with prompt: "I want to add a health check endpoint to omniclaude"
2. After the brainstorming session, a design file should exist
3. Pass that design file to `@11-writing-plans` to generate a plan
4. After the plan is written, pass the plan file to `@12-plan-ticket` to generate a ticket template

### Chain Pass Criteria

- [ ] Design file written to `docs/plans/YYYY-MM-DD-*-design.md`
- [ ] Plan file written to `docs/plans/YYYY-MM-DD-*.md` (separate from design file)
- [ ] Ticket template output as YAML with `repo: "omniclaude"`
- [ ] Each handoff line references the actual artifact path (not "paste above")
- [ ] No external service called at any point in the chain

---

## Phase 4: Integration Gap Analysis

Attempt to port `decompose-epic/SKILL.md` to a Cursor rule. You will find it cannot be done without Bucket 3 deps.

Write `adapter-interface.md` documenting:

1. **Which external services are required** and why (Linear MCP, Python validator)
2. **What the adapter input schema should be** for a `decompose-epic` call
3. **What the adapter output schema should be** (based on the frozen contract in `docs/ARCHITECTURE.md`)
4. **What the fail-soft fallback should say** when Linear is unavailable

### Pass Criteria

- [ ] All 3 Bucket 3 dependencies correctly identified (Linear MCP, Python validator with omnibase_core, Kafka routing)
- [ ] Input schema for decompose-epic defined with correct field names and types
- [ ] Fail-soft description is specific ("Complete manually: open Linear, navigate to OMN-XXXX, create child tickets")
- [ ] Student does NOT attempt to simulate Linear responses inline in the rule

---

## Phase 5: Demo (methodology chain)

Run a complete live Cursor session demonstrating the full chain:

1. Start fresh in `cursor-omninode/`
2. Brainstorm an idea (use any of the test prompts or your own)
3. Generate the implementation plan from the design doc
4. Generate the ticket template from the plan

For **Bucket 3 / decompose-epic**, stop at Phase 4’s written `adapter-interface.md` (or describe manual Linear steps). There is no in-repo `20-adapter-stub.mdc` or `tests/rubrics/adapter-stub.md` in this repository baseline.

### Deliverable

Zip the entire starter folder (including any `docs/plans/` files you wrote during testing) per your course instructions.

---

## Trigger Mode Guidance

Cursor rules auto-activate based on the keywords in the `description` frontmatter field. However,
keyword matching is not perfectly deterministic — the same prompt may or may not auto-trigger a rule.

**Both trigger modes are equally valid:**

- **Auto-activation:** Rule fires automatically when description keywords match your prompt
- **@mention:** Type `@10-brainstorming` in Composer to explicitly invoke the rule

Graders will not penalize for requiring @mention. The rubric only requires that the rule
activates within the first response, by either method.
