# Cursor rules (`.mdc`)

OmniCursor **behavior surface** for the model. Rules `00` and `01` are **always on**; others activate on keywords or explicit `@mention`.

| File | Role |
|------|------|
| [`00-omninode-concepts.mdc`](./00-omninode-concepts.mdc) | ONEX vocabulary, buckets 1–3, pipeline stages. |
| [`01-codebase-research.mdc`](./01-codebase-research.mdc) | Bounded file-reading policy for agents. |
| [`02-no-secrets-in-commits.mdc`](./02-no-secrets-in-commits.mdc) | No API keys, tokens, or real env values in repo or suggested commits. |
| [`10-brainstorming.mdc`](./10-brainstorming.mdc) | Bucket 1 — idea → design doc. |
| [`11-writing-plans.mdc`](./11-writing-plans.mdc) | Bucket 1 — design → implementation plan. |
| [`12-plan-ticket.mdc`](./12-plan-ticket.mdc) | Bucket 2 — plan → YAML ticket template. |
| [`13-systematic-debugging.mdc`](./13-systematic-debugging.mdc) | Debugging methodology + hook/skill alignment. |
| [`14-pr-review.mdc`](./14-pr-review.mdc) | PR / merge-readiness review + severity rubric. |
| [`15-handoff.mdc`](./15-handoff.mdc) | Session continuity — structured handoff manifest. |

**Skills:** Rules direct the model to read `.cursor/skills/<name>/SKILL.md`. Structured routing/compliance for tests lives in `src/omnicursor/`. See [docs/QUICKSTART.md](../../docs/QUICKSTART.md).

**Teaching / capstone:** [docs/dev/STUDENT_GUIDE.md](../../docs/dev/STUDENT_GUIDE.md), [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) (bucket model; Bucket 3 is conceptual — no `adapter-stub` rule in this repo).

**Tests:** Prompts under [`../../tests/prompts/`](../../tests/prompts/), rubrics under [`../../tests/rubrics/`](../../tests/rubrics/).
