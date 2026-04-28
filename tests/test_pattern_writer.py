"""Tests for outcome-driven pattern learning (pattern_writer.py)."""

from __future__ import annotations

import json
import time

from omnicursor.pattern_writer import (
    HARD_FLOOR,
    INITIAL_WEIGHT,
    MAX_PATTERNS_PER_DOMAIN,
    WEIGHT_CAP,
    WEIGHT_INCREMENT,
    _agent_to_domain,
    _evict_overflow,
    _upsert_pattern,
    extract_patterns_from_events,
    write_session_patterns,
)


# ---------------------------------------------------------------------------
# _agent_to_domain
# ---------------------------------------------------------------------------


def test_agent_to_domain_strips_prefix():
    assert _agent_to_domain("agent-debugging") == "debugging"


def test_agent_to_domain_replaces_hyphens():
    assert _agent_to_domain("systematic-debugging") == "systematic_debugging"


def test_agent_to_domain_passthrough():
    assert _agent_to_domain("brainstorming") == "brainstorming"


# ---------------------------------------------------------------------------
# extract_patterns_from_events
# ---------------------------------------------------------------------------


def _prompt_event(agent: str, score: float, snippet: str) -> dict:
    return {
        "event": "prompt_classified",
        "matched_agent": agent,
        "score": score,
        "prompt_snippet": snippet,
    }


def test_extract_skips_polymorphic_agent():
    events = [_prompt_event("polymorphic-agent", 0.9, "debug this function")]
    result = extract_patterns_from_events(events, files_edited=1)
    assert result == []


def test_extract_skips_below_hard_floor():
    events = [_prompt_event("debugging", HARD_FLOOR - 0.01, "debug this")]
    result = extract_patterns_from_events(events, files_edited=1)
    assert result == []


def test_extract_skips_empty_snippet():
    events = [_prompt_event("debugging", 0.9, "")]
    result = extract_patterns_from_events(events, files_edited=1)
    assert result == []


def test_extract_skips_non_prompt_events():
    events = [{"event": "file_edited", "file_path": "src/foo.py"}]
    result = extract_patterns_from_events(events, files_edited=1)
    assert result == []


def test_extract_returns_candidate_above_floor():
    events = [_prompt_event("debugging", 0.8, "TypeError on line 42")]
    result = extract_patterns_from_events(events, files_edited=1)
    assert len(result) == 1
    assert result[0]["domain"] == "debugging"
    assert isinstance(result[0]["keywords"], list)
    assert len(result[0]["keywords"]) > 0


def test_extract_multiple_events():
    events = [
        _prompt_event("debugging", 0.8, "TypeError on line 42"),
        _prompt_event("brainstorming", 0.75, "brainstorm API design options"),
    ]
    result = extract_patterns_from_events(events, files_edited=1)
    assert len(result) == 2
    domains = {r["domain"] for r in result}
    assert "debugging" in domains
    assert "brainstorming" in domains


# ---------------------------------------------------------------------------
# _upsert_pattern
# ---------------------------------------------------------------------------


def test_upsert_inserts_new_pattern():
    now = time.time()
    result = _upsert_pattern([], "debugging", ["typeerror", "line"], "desc", now)
    assert len(result) == 1
    assert result[0]["weight"] == INITIAL_WEIGHT
    assert result[0]["success_count"] == 1
    assert result[0]["domain"] == "debugging"


def test_upsert_increments_existing_pattern():
    now = time.time()
    existing = _upsert_pattern([], "debugging", ["typeerror", "line"], "desc", now)
    updated = _upsert_pattern(existing, "debugging", ["typeerror", "line"], "desc", now)
    assert len(updated) == 1
    assert updated[0]["weight"] == round(INITIAL_WEIGHT + WEIGHT_INCREMENT, 3)
    assert updated[0]["success_count"] == 2


def test_upsert_caps_weight_at_max():
    now = time.time()
    patterns = [{
        "pattern": "line typeerror",
        "domain": "debugging",
        "weight": WEIGHT_CAP,
        "success_count": 10,
        "last_seen": now,
        "description": "desc",
    }]
    result = _upsert_pattern(patterns, "debugging", ["typeerror", "line"], "desc", now)
    assert result[0]["weight"] == WEIGHT_CAP


def test_upsert_different_domain_creates_new():
    now = time.time()
    existing = _upsert_pattern([], "debugging", ["typeerror"], "desc", now)
    result = _upsert_pattern(existing, "brainstorming", ["typeerror"], "desc", now)
    assert len(result) == 2


# ---------------------------------------------------------------------------
# _evict_overflow
# ---------------------------------------------------------------------------


def test_evict_keeps_highest_weight_patterns():
    now = time.time()
    patterns = [
        {"domain": "debugging", "pattern": f"p{i}", "weight": i * 0.05,
         "success_count": 1, "last_seen": now, "description": ""}
        for i in range(MAX_PATTERNS_PER_DOMAIN + 5)
    ]
    result = _evict_overflow(patterns)
    debugging = [p for p in result if p["domain"] == "debugging"]
    assert len(debugging) == MAX_PATTERNS_PER_DOMAIN
    weights = [p["weight"] for p in debugging]
    assert weights == sorted(weights, reverse=True)


# ---------------------------------------------------------------------------
# write_session_patterns (integration)
# ---------------------------------------------------------------------------


def test_write_skips_when_no_files_edited(tmp_path):
    events = [_prompt_event("debugging", 0.8, "debug TypeError")]
    pf = tmp_path / "learned_patterns.json"
    written = write_session_patterns(pf, events, files_edited=0)
    assert written == 0
    assert not pf.exists()


def test_write_skips_when_no_decisive_events(tmp_path):
    events = [_prompt_event("polymorphic-agent", 0.9, "debug this")]
    pf = tmp_path / "learned_patterns.json"
    written = write_session_patterns(pf, events, files_edited=2)
    assert written == 0


def test_write_creates_file_with_patterns(tmp_path):
    events = [_prompt_event("debugging", 0.85, "TypeError in parser line 42")]
    pf = tmp_path / "learned_patterns.json"
    written = write_session_patterns(pf, events, files_edited=1)
    assert written == 1
    assert pf.exists()
    data = json.loads(pf.read_text())
    assert len(data["patterns"]) == 1
    assert data["patterns"][0]["domain"] == "debugging"
    assert data["patterns"][0]["weight"] == INITIAL_WEIGHT


def test_write_increments_on_repeated_success(tmp_path):
    events = [_prompt_event("debugging", 0.85, "TypeError in parser line 42")]
    pf = tmp_path / "learned_patterns.json"
    write_session_patterns(pf, events, files_edited=1)
    write_session_patterns(pf, events, files_edited=1)
    data = json.loads(pf.read_text())
    assert data["patterns"][0]["success_count"] == 2
    assert data["patterns"][0]["weight"] == round(INITIAL_WEIGHT + WEIGHT_INCREMENT, 3)


def test_write_multiple_domains(tmp_path):
    events = [
        _prompt_event("debugging", 0.85, "TypeError in parser"),
        _prompt_event("brainstorming", 0.78, "brainstorm design options"),
    ]
    pf = tmp_path / "learned_patterns.json"
    written = write_session_patterns(pf, events, files_edited=2)
    assert written == 2
    data = json.loads(pf.read_text())
    domains = {p["domain"] for p in data["patterns"]}
    assert "debugging" in domains
    assert "brainstorming" in domains
