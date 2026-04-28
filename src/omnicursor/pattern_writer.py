"""Outcome-driven pattern learning — writes learned patterns from successful sessions.

Called by the stop hook when a session ends with outcome 'success'.
Extracts routing signals from prompt_classified events and writes them to
learned_patterns.json so they are injected in future sessions.

Pattern weight mechanics:
  - New pattern: weight = 0.60
  - Each repeated success: weight += 0.05, capped at 0.95
  - Patterns not seen in DECAY_DAYS: weight -= 0.10 per day past threshold
  - Max MAX_PATTERNS_PER_DOMAIN patterns per domain (oldest evicted)

Stdlib-only. No pip dependencies.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List

# v0 calibration — chosen to match routing HARD_FLOOR; patterns from low-confidence
# classifications are too noisy to learn from. Tune with scoring eval harness.
HARD_FLOOR: float = 0.55

# v0 calibration — moderate initial confidence so new patterns matter but don't
# dominate. Each repeated success adds 0.05 (takes 7 successes to reach cap).
# Neither value has been evaluated against session outcome data.
INITIAL_WEIGHT: float = 0.60
WEIGHT_INCREMENT: float = 0.05
WEIGHT_CAP: float = 0.95

# Eviction floor — patterns below this are removed regardless of recency.
WEIGHT_FLOOR: float = 0.10

# v0 calibration — 30-day window before decay, 0.10 per period.
# Not tuned against real session frequency data.
DECAY_DAYS: int = 30
DECAY_AMOUNT: float = 0.10

# Cap per domain — prevents any single domain from monopolizing the cache.
MAX_PATTERNS_PER_DOMAIN: int = 20

STOPWORDS: frozenset = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "has", "have", "i", "in", "is", "it", "my", "not", "of", "on",
    "or", "the", "this", "that", "to", "was", "we", "with", "you",
})


def _keywords(text: str) -> List[str]:
    return [
        w for w in re.findall(r"\b\w+\b", text.lower())
        if w not in STOPWORDS and len(w) > 2
    ]


def _agent_to_domain(agent_name: str) -> str:
    domain = agent_name.lower()
    for prefix in ("agent-", "omnicursor-"):
        if domain.startswith(prefix):
            domain = domain[len(prefix):]
    return domain.replace("-", "_")


def _load_patterns(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        raw = data.get("patterns", [])
        return [p for p in raw if isinstance(p, dict)]
    except (json.JSONDecodeError, OSError):
        return []


def _save_patterns(path: Path, patterns: List[Dict[str, Any]]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"patterns": patterns}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        pass


def _decay_patterns(patterns: List[Dict[str, Any]], now: float) -> List[Dict[str, Any]]:
    """Reduce weight of patterns not seen recently."""
    result = []
    for p in patterns:
        last_seen = p.get("last_seen", now)
        days_old = (now - last_seen) / 86400
        if days_old > DECAY_DAYS:
            days_past = days_old - DECAY_DAYS
            decayed = p["weight"] - DECAY_AMOUNT * (days_past / DECAY_DAYS)
            p = {**p, "weight": max(WEIGHT_FLOOR, round(decayed, 3))}
        result.append(p)
    return result


def _upsert_pattern(
    patterns: List[Dict[str, Any]],
    domain: str,
    keywords: List[str],
    description: str,
    now: float,
) -> List[Dict[str, Any]]:
    """Insert or update a pattern. Returns updated list."""
    pattern_key = " ".join(sorted(keywords[:5]))

    for i, p in enumerate(patterns):
        if p.get("domain") == domain and p.get("pattern") == pattern_key:
            updated = {
                **p,
                "weight": min(WEIGHT_CAP, round(p.get("weight", INITIAL_WEIGHT) + WEIGHT_INCREMENT, 3)),
                "success_count": p.get("success_count", 1) + 1,
                "last_seen": now,
                "description": description,
            }
            result = list(patterns)
            result[i] = updated
            return result

    new_pattern: Dict[str, Any] = {
        "pattern": pattern_key,
        "domain": domain,
        "weight": INITIAL_WEIGHT,
        "success_count": 1,
        "last_seen": now,
        "description": description,
    }
    return patterns + [new_pattern]


def _evict_overflow(patterns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Keep at most MAX_PATTERNS_PER_DOMAIN per domain, evicting lowest weight."""
    by_domain: Dict[str, List[Dict[str, Any]]] = {}
    for p in patterns:
        d = p.get("domain", "general")
        by_domain.setdefault(d, []).append(p)

    result = []
    for domain_patterns in by_domain.values():
        domain_patterns.sort(key=lambda x: x.get("weight", 0), reverse=True)
        result.extend(domain_patterns[:MAX_PATTERNS_PER_DOMAIN])
    return result


def extract_patterns_from_events(
    events: List[Dict[str, Any]],
    files_edited: int,
) -> List[Dict[str, Any]]:
    """Extract candidate patterns from session events.

    Only extracts from prompt_classified events where:
    - score >= HARD_FLOOR (decisive routing, not fallback)
    - matched_agent is not polymorphic-agent
    - prompt_snippet is non-empty
    """
    candidates = []
    for evt in events:
        if evt.get("event") != "prompt_classified":
            continue
        agent = evt.get("matched_agent", "")
        score = evt.get("score", 0.0)
        snippet = evt.get("prompt_snippet", "")

        if not agent or agent == "polymorphic-agent":
            continue
        if score < HARD_FLOOR:
            continue
        if not snippet:
            continue

        keywords = _keywords(snippet)
        if not keywords:
            continue

        domain = _agent_to_domain(agent)
        description = "Auto-learned: {} → {} (score {:.2f})".format(
            snippet[:60], agent, score
        )
        candidates.append({
            "domain": domain,
            "keywords": keywords,
            "description": description,
        })

    return candidates


def write_session_patterns(
    patterns_file: Path,
    events: List[Dict[str, Any]],
    files_edited: int,
) -> int:
    """Extract patterns from events and persist to learned_patterns.json.

    Only runs when:
    - files_edited > 0 (real work happened)
    - at least one decisive routing event exists

    Returns the number of patterns written (new + updated).
    """
    if files_edited == 0:
        return 0

    candidates = extract_patterns_from_events(events, files_edited)
    if not candidates:
        return 0

    now = time.time()
    existing = _load_patterns(patterns_file)
    existing = _decay_patterns(existing, now)

    written = 0
    for c in candidates:
        existing = _upsert_pattern(
            existing,
            domain=c["domain"],
            keywords=c["keywords"],
            description=c["description"],
            now=now,
        )
        written += 1

    existing = _evict_overflow(existing)
    _save_patterns(patterns_file, existing)
    return written
