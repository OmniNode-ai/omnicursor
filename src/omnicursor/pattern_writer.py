"""Outcome-driven pattern learning — tracks injections and learns from successful sessions.

Called by the stop hook after every session (any outcome).

Metric updates (any outcome):
  - injection_count incremented for each known pattern_id in injected_pattern_ids.
  - utilization_successes incremented only when session_outcome == 'success'.

Pattern learning (success + files_edited > 0 only):
  - Extracts routing signals from prompt_classified events.
  - Upserts learned patterns; weight boosted by 1.5x multiplier when pattern was injected.

Pattern weight mechanics:
  - New pattern: weight = 0.60
  - Each repeated success: weight += 0.05, capped at 0.95
  - Patterns not seen in DECAY_DAYS: weight -= 0.10 per day past threshold
  - Max MAX_PATTERNS_PER_DOMAIN patterns per domain (oldest evicted)
  - Patterns injected often but rarely succeeding are evicted by utilization rate

Stdlib-only. No pip dependencies.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List

# Secret redaction (A5): prompt-derived snippets must never land in
# learned_patterns.json unredacted. The canonical stdlib port lives in the
# hooks lib (on sys.path when invoked from the stop hook); fall back to
# loading it by path for package contexts (tests, CI) in the repo checkout.
try:
    from redaction import redact_secrets  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - exercised via the package import path
    import importlib.util as _ilu

    _redaction_path = (
        Path(__file__).resolve().parents[2]
        / ".cursor"
        / "hooks"
        / "lib"
        / "redaction.py"
    )
    _spec = _ilu.spec_from_file_location("redaction", _redaction_path)
    _redaction = _ilu.module_from_spec(_spec)  # type: ignore[arg-type]
    _spec.loader.exec_module(_redaction)  # type: ignore[union-attr]
    redact_secrets = _redaction.redact_secrets

# v0 calibration — chosen to match routing HARD_FLOOR; patterns from low-confidence
# classifications are too noisy to learn from. Tune with scoring eval harness.
HARD_FLOOR: float = 0.55

# v0 calibration — moderate initial confidence so new patterns matter but don't
# dominate. Each repeated success adds 0.05 (takes 7 successes to reach cap).
# Neither value has been evaluated against session outcome data.
INITIAL_WEIGHT: float = 0.60
WEIGHT_INCREMENT: float = 0.05
WEIGHT_CAP: float = 0.95
UTILIZATION_SUCCESS_WEIGHT_MULTIPLIER: float = 1.5

# Eviction floor — patterns below this are removed regardless of recency.
WEIGHT_FLOOR: float = 0.10

# v0 calibration — 30-day window before decay, 0.10 per period.
# Not tuned against real session frequency data.
DECAY_DAYS: int = 30
DECAY_AMOUNT: float = 0.10

# Cap per domain — prevents any single domain from monopolizing the cache.
MAX_PATTERNS_PER_DOMAIN: int = 20
UTILIZATION_EVICT_MIN_INJECTIONS: int = 10
UTILIZATION_EVICT_MIN_RATE: float = 0.2

STOPWORDS: frozenset = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "has",
        "have",
        "i",
        "in",
        "is",
        "it",
        "my",
        "not",
        "of",
        "on",
        "or",
        "the",
        "this",
        "that",
        "to",
        "was",
        "we",
        "with",
        "you",
    }
)


def _make_pattern_id(domain: str, pattern_key: str) -> str:
    raw = f"{domain}:{pattern_key}".encode("utf-8")
    # Content-address only, never a security boundary (bandit B324).
    return "auto-" + hashlib.sha1(raw, usedforsecurity=False).hexdigest()[:12]


def _keywords(text: str) -> List[str]:
    return [
        w
        for w in re.findall(r"\b\w+\b", text.lower())
        if w not in STOPWORDS and len(w) > 2
    ]


def _agent_to_domain(agent_name: str) -> str:
    domain = agent_name.lower()
    for prefix in ("agent-", "omnicursor-"):
        if domain.startswith(prefix):
            domain = domain[len(prefix) :]
    return domain.replace("-", "_")


def _load_patterns(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        raw = data.get("patterns", [])
        result: List[Dict[str, Any]] = []
        for p in raw:
            if not isinstance(p, dict):
                continue
            record = {
                **p,
                "injection_count": int(p.get("injection_count", 0)),
                "utilization_successes": int(p.get("utilization_successes", 0)),
            }
            if not record.get("pattern_id"):
                record["pattern_id"] = _make_pattern_id(
                    record.get("domain", "general"),
                    record.get("pattern", ""),
                )
            result.append(record)
        return result
    except (json.JSONDecodeError, OSError):
        return []


def _save_patterns(path: Path, patterns: List[Dict[str, Any]]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"patterns": patterns}, indent=2, ensure_ascii=False)
        fd, tmp_name = tempfile.mkstemp(
            prefix=path.name + ".",
            suffix=".tmp",
            dir=str(path.parent),
        )
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(payload)
            os.replace(tmp_path, path)
        except Exception:
            try:
                tmp_path.unlink()
            except OSError:
                pass
            raise
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
    *,
    injected_success: bool = False,
) -> List[Dict[str, Any]]:
    """Insert or update a pattern. Returns updated list."""
    pattern_key = " ".join(sorted(keywords[:5]))

    for i, p in enumerate(patterns):
        if p.get("domain") == domain and p.get("pattern") == pattern_key:
            increment = WEIGHT_INCREMENT * (
                UTILIZATION_SUCCESS_WEIGHT_MULTIPLIER if injected_success else 1.0
            )
            updated = {
                **p,
                "weight": min(
                    WEIGHT_CAP, round(p.get("weight", INITIAL_WEIGHT) + increment, 3)
                ),
                "success_count": p.get("success_count", 1) + 1,
                "injection_count": int(p.get("injection_count", 0))
                + (1 if injected_success else 0),
                "utilization_successes": int(p.get("utilization_successes", 0))
                + (1 if injected_success else 0),
                "last_seen": now,
                "description": description,
            }
            result = list(patterns)
            result[i] = updated
            return result

    new_pattern: Dict[str, Any] = {
        "pattern_id": _make_pattern_id(domain, pattern_key),
        "pattern": pattern_key,
        "domain": domain,
        "weight": INITIAL_WEIGHT,
        "success_count": 1,
        "injection_count": 1 if injected_success else 0,
        "utilization_successes": 1 if injected_success else 0,
        "last_seen": now,
        "description": description,
    }
    return patterns + [new_pattern]


def _evict_low_utilization(patterns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Drop patterns that are injected often but rarely lead to success."""
    result: List[Dict[str, Any]] = []
    for p in patterns:
        injection_count = int(p.get("injection_count", 0))
        utilization_successes = int(p.get("utilization_successes", 0))
        if injection_count > UTILIZATION_EVICT_MIN_INJECTIONS:
            rate = utilization_successes / injection_count if injection_count else 0.0
            if rate < UTILIZATION_EVICT_MIN_RATE:
                continue
        result.append(p)
    return result


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
            redact_secrets(snippet)[:60], agent, score
        )
        candidates.append(
            {
                "domain": domain,
                "keywords": keywords,
                "description": description,
                "injected": int(evt.get("patterns_injected", 0)) > 0,
            }
        )

    return candidates


def write_session_patterns(
    patterns_file: Path,
    events: List[Dict[str, Any]],
    files_edited: int,
    session_outcome: str = "success",
) -> int:
    """Update pattern metrics and learn from session events.

    - Any outcome: increments injection_count for each known injected pattern_id.
    - success only: increments utilization_successes and updates weight; learns
      new patterns from prompt_snippet when files_edited > 0.

    Returns count of records changed (metric updates + new/upserted patterns).
    """
    now = time.time()
    existing = _load_patterns(patterns_file)
    existing = _decay_patterns(existing, now)

    # Build an index for O(1) lookup by pattern_id.
    id_index: Dict[str, int] = {
        p["pattern_id"]: i for i, p in enumerate(existing) if p.get("pattern_id")
    }

    changed = 0

    # --- Metric updates by injected_pattern_ids ---
    for evt in events:
        if evt.get("event") != "prompt_classified":
            continue
        raw_ids = evt.get("injected_pattern_ids", [])
        if not raw_ids:
            continue
        seen_in_event: set = set()
        for pid in raw_ids:
            if not pid or pid in seen_in_event:
                continue
            seen_in_event.add(pid)
            idx = id_index.get(pid)
            if idx is None:
                continue
            p = existing[idx]
            p = {**p, "injection_count": p["injection_count"] + 1}
            if session_outcome == "success":
                increment = WEIGHT_INCREMENT * UTILIZATION_SUCCESS_WEIGHT_MULTIPLIER
                p = {
                    **p,
                    "utilization_successes": p["utilization_successes"] + 1,
                    "weight": min(
                        WEIGHT_CAP,
                        round(p.get("weight", INITIAL_WEIGHT) + increment, 3),
                    ),
                    "last_seen": now,
                }
            existing[idx] = p
            changed += 1

    # --- Learn new patterns from prompt_snippet (success + files_edited > 0 only) ---
    if session_outcome == "success" and files_edited > 0:
        candidates = extract_patterns_from_events(events, files_edited)
        for c in candidates:
            existing = _upsert_pattern(
                existing,
                domain=c["domain"],
                keywords=c["keywords"],
                description=c["description"],
                now=now,
                injected_success=False,
            )
            changed += 1

    if not existing and changed == 0:
        return 0

    existing = _evict_low_utilization(existing)
    existing = _evict_overflow(existing)
    _save_patterns(patterns_file, existing)
    return changed
