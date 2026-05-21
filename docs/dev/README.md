# Developer docs

Active reference documents for contributors and CI. All files here are either referenced by code comments, CLAUDE.md, or contain architectural decisions that inform ongoing work.

| File | What it is |
|------|------------|
| [OMNICURSOR_IMPLEMENTATION_BRIEF.md](./OMNICURSOR_IMPLEMENTATION_BRIEF.md) | Implementation decisions and copy map from OmniClaude. Referenced by CLAUDE.md source-of-truth hierarchy. |
| [DEVELOPER.md](./DEVELOPER.md) | Starter-kit ↔ backend mapping. |
| [ADR-hook-first-architecture.md](./ADR-hook-first-architecture.md) | Architectural decision record: rules vs hooks vs library ownership. |
| [OMNICURSOR_NODE_CONTRACTS.md](./OMNICURSOR_NODE_CONTRACTS.md) | Per-node `contract.yaml` under `src/omnicursor/nodes/`. Referenced by `src/omnicursor/nodes/__init__.py`. |
| [OMNICLAUDE_TO_CURSOR_PORT.md](./OMNICLAUDE_TO_CURSOR_PORT.md) | OmniClaude → Cursor port decisions: hook vs library planes, shared pattern module. Referenced by hook scripts. |
| [OMNICURSOR_SYSTEM_DESIGN.md](./OMNICURSOR_SYSTEM_DESIGN.md) | Systems design diagrams (Mermaid): IDE layers + optional OmniNode integration. |
| [ROUTING_DEDUPLICATION.md](./ROUTING_DEDUPLICATION.md) | How scoring logic is shared between hooks and the Python library. Referenced by `scoring.py` and `agent_scoring.py`. |
| [HOW_TO_RUN_IN_CURSOR.md](./HOW_TO_RUN_IN_CURSOR.md) | Walkthrough for running OmniCursor inside Cursor IDE. |
| [OMNINODE_STACK.md](./OMNINODE_STACK.md) | What `compose.yaml` starts, optional profiles, remote build contexts. |
| [explanation.md](./explanation.md) | Plain-language (ES) overview of OmniCursor for new contributors. |
| [INTELLIGENCE_LAYER_CURRENT_STATE_AND_OPTIONS.md](./INTELLIGENCE_LAYER_CURRENT_STATE_AND_OPTIONS.md) | Intelligence layer options (A/B/C), current wiring, roadmap. |

Completed planning docs, sponsor session notes, Option A closure prompts, session handoffs, and capstone artifacts are in [`../archive/`](../archive/README.md).
