# Agent Routing Deduplication

## Problem

Three independent copies of the three-strategy agent scoring logic existed before this fix:

| File | Role |
|------|------|
| `.cursor/hooks/on_prompt.py` | Test-facing hook (imported by `tests/`) |
| `.cursor/hooks/scripts/user-prompt-submit.py` | Cursor runtime hook (`hooks.json`) |
| `src/omnicursor/agents.py` | Python library (`omnicursor` package) |

Each file had its own `_fuzzy_threshold`, `_score_agent`, `HARD_FLOOR`, and `_STOPWORDS`.
They were functionally identical at the time but were maintained independently.
Any scoring fix or new trigger strategy required three separate edits, and any
divergence would produce silent behavioral differences between what the tests
cover and what Cursor actually runs.

The STOPWORDS divergence was the first symptom: `agents.py` used its own
`_STOPWORDS` frozenset while `scripts/user-prompt-submit.py` imported `STOPWORDS`
from `prompt_pattern_selection.py`. Both sets had the same 22 words at time of
writing but there was no enforcement.

## Fix

**Canonical source:** `.cursor/hooks/lib/agent_scoring.py` (stdlib only).

This module exports:

- `HARD_FLOOR: float` — minimum score threshold (0.55)
- `STOPWORDS: frozenset[str]` — shared stopword list
- `extract_keywords(text) -> list[str]` — tokenizer used for strategy 3
- `fuzzy_threshold(trigger) -> float` — length-aware SequenceMatcher threshold
- `score_agent(prompt_lower, prompt_words, agent) -> (float, str)` — full three-strategy scorer

### How each consumer loads it

**Hook files** (stdlib only, must not import `omnicursor`):

```python
# Already have lib/ in sys.path from their own sys.path.insert.
from agent_scoring import HARD_FLOOR, score_agent
```

`on_prompt.py` adds `lib/` to its path alongside its existing `parent` insert:
```python
sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
```

**Python library** (`src/omnicursor/agents.py`):

Uses the same importlib-by-path bridge established by `prompt_pattern_read.py`.
The library must not import hook files directly (that would make `omnicursor`
a hook dependency). Instead:

```python
def _load_agent_scoring() -> ModuleType:
    path = Path(__file__).resolve().parents[2] / ".cursor" / "hooks" / "lib" / "agent_scoring.py"
    ...
    spec.loader.exec_module(mod)
    return mod

_as = _load_agent_scoring()
HARD_FLOOR: float = _as.HARD_FLOOR
_STOPWORDS: frozenset[str] = _as.STOPWORDS
_score_agent = _as.score_agent
_fuzzy_threshold = _as.fuzzy_threshold
```

The public API of `agents.py` (`match_agent`, `match_agent_candidates`,
`get_agent_context`, etc.) is unchanged.

## Architecture constraint

`agent_scoring.py` has **no imports from other lib/ files** to avoid chained
importlib loads. `STOPWORDS` is defined inline with a comment pointing to the
identical definition in `prompt_pattern_selection.py`. If the stopword list
ever needs to change, update both files together.

## Files changed

```
.cursor/hooks/lib/agent_scoring.py       ← new canonical source
.cursor/hooks/on_prompt.py               ← removed _fuzzy_threshold, _score_agent, HARD_FLOOR, _STOPWORDS, _extract_keywords
.cursor/hooks/scripts/user-prompt-submit.py ← removed _fuzzy_threshold, _score_agent, HARD_FLOOR
src/omnicursor/agents.py                 ← added importlib bridge; removed duplicate functions
docs/dev/ROUTING_DEDUPLICATION.md        ← this file
```

## Testing

All 397 tests pass before and after the change (`pytest tests/ -q`).
The test suite exercises `classify_prompt` via `on_prompt.py` and
`match_agent_candidates` via `agents.py`, so both load paths are covered.
