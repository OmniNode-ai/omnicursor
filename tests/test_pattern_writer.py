"""Tests for outcome-driven pattern learning (pattern_writer.py)."""

from __future__ import annotations

import json
import time

from omnicursor.pattern_writer import (
    HARD_FLOOR,
    INITIAL_WEIGHT,
    MAX_PATTERNS_PER_DOMAIN,
    UTILIZATION_EVICT_MIN_INJECTIONS,
    UTILIZATION_SUCCESS_WEIGHT_MULTIPLIER,
    WEIGHT_CAP,
    WEIGHT_INCREMENT,
    _agent_to_domain,
    _evict_low_utilization,
    _evict_overflow,
    _make_pattern_id,
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


def _prompt_event_with_injection(
    agent: str, score: float, snippet: str, patterns_injected: int,
) -> dict:
    event = _prompt_event(agent, score, snippet)
    event["patterns_injected"] = patterns_injected
    return event


def _prompt_event_with_pattern_ids(
    agent: str, score: float, snippet: str, pattern_ids: list,
) -> dict:
    event = _prompt_event(agent, score, snippet)
    event["patterns_injected"] = len(pattern_ids)
    event["injected_pattern_ids"] = pattern_ids
    return event


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


def test_extract_redacts_secrets_in_description():
    # A5: a snippet carrying a secret must never land in learned_patterns.json
    # unredacted (defense-in-depth — the log-time snippet is also sanitized).
    secret = "sk-abcdef1234567890ABCDEF1234"
    events = [_prompt_event("debugging", 0.8, "debug {}".format(secret))]
    result = extract_patterns_from_events(events, files_edited=1)
    assert len(result) == 1
    assert secret not in result[0]["description"]
    assert "***REDACTED***" in result[0]["description"]


# ---------------------------------------------------------------------------
# _upsert_pattern
# ---------------------------------------------------------------------------


def test_upsert_inserts_new_pattern():
    now = time.time()
    result = _upsert_pattern([], "debugging", ["typeerror", "line"], "desc", now)
    assert len(result) == 1
    assert result[0]["weight"] == INITIAL_WEIGHT
    assert result[0]["success_count"] == 1
    assert result[0]["injection_count"] == 0
    assert result[0]["utilization_successes"] == 0
    assert result[0]["domain"] == "debugging"


def test_upsert_increments_existing_pattern():
    now = time.time()
    existing = _upsert_pattern([], "debugging", ["typeerror", "line"], "desc", now)
    updated = _upsert_pattern(existing, "debugging", ["typeerror", "line"], "desc", now)
    assert len(updated) == 1
    assert updated[0]["weight"] == round(INITIAL_WEIGHT + WEIGHT_INCREMENT, 3)
    assert updated[0]["success_count"] == 2


def test_upsert_increments_utilization_on_successful_injection():
    now = time.time()
    existing = _upsert_pattern([], "debugging", ["typeerror", "line"], "desc", now)
    updated = _upsert_pattern(
        existing,
        "debugging",
        ["typeerror", "line"],
        "desc",
        now,
        injected_success=True,
    )
    assert updated[0]["injection_count"] == 1
    assert updated[0]["utilization_successes"] == 1


def test_upsert_injected_success_gains_weight_faster():
    now = time.time()
    base = _upsert_pattern([], "debugging", ["typeerror", "line"], "desc", now)

    normal = _upsert_pattern(base, "debugging", ["typeerror", "line"], "desc", now)
    injected = _upsert_pattern(
        base,
        "debugging",
        ["typeerror", "line"],
        "desc",
        now,
        injected_success=True,
    )

    expected_injected_weight = round(
        INITIAL_WEIGHT + (WEIGHT_INCREMENT * UTILIZATION_SUCCESS_WEIGHT_MULTIPLIER),
        3,
    )
    assert normal[0]["weight"] == round(INITIAL_WEIGHT + WEIGHT_INCREMENT, 3)
    assert injected[0]["weight"] == expected_injected_weight
    assert injected[0]["weight"] > normal[0]["weight"]


def test_upsert_caps_weight_at_max():
    now = time.time()
    patterns = [{
        "pattern": "line typeerror",
        "domain": "debugging",
        "weight": WEIGHT_CAP,
        "success_count": 10,
        "injection_count": 0,
        "utilization_successes": 0,
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
        {
            "domain": "debugging",
            "pattern": f"p{i}",
            "weight": i * 0.05,
            "success_count": 1,
            "injection_count": 0,
            "utilization_successes": 0,
            "last_seen": now,
            "description": "",
        }
        for i in range(MAX_PATTERNS_PER_DOMAIN + 5)
    ]
    result = _evict_overflow(patterns)
    debugging = [p for p in result if p["domain"] == "debugging"]
    assert len(debugging) == MAX_PATTERNS_PER_DOMAIN
    weights = [p["weight"] for p in debugging]
    assert weights == sorted(weights, reverse=True)


def test_evict_low_utilization_removes_pattern():
    patterns = [
        {
            "domain": "debugging",
            "pattern": "evict-me",
            "weight": 0.7,
            "success_count": 3,
            "injection_count": UTILIZATION_EVICT_MIN_INJECTIONS + 1,
            "utilization_successes": 1,
            "last_seen": time.time(),
            "description": "",
        },
        {
            "domain": "debugging",
            "pattern": "keep-me",
            "weight": 0.7,
            "success_count": 3,
            "injection_count": UTILIZATION_EVICT_MIN_INJECTIONS + 1,
            "utilization_successes": 3,
            "last_seen": time.time(),
            "description": "",
        },
    ]
    kept = _evict_low_utilization(patterns)
    assert len(kept) == 1
    assert kept[0]["pattern"] == "keep-me"


# ---------------------------------------------------------------------------
# write_session_patterns (integration)
# ---------------------------------------------------------------------------


def test_write_skips_when_no_files_edited(tmp_path):
    events = [_prompt_event("debugging", 0.8, "debug TypeError")]
    pf = tmp_path / "learned_patterns.json"
    written = write_session_patterns(pf, events, files_edited=0, session_outcome="success")
    assert written == 0
    assert not pf.exists()


def test_write_skips_when_no_decisive_events(tmp_path):
    events = [_prompt_event("polymorphic-agent", 0.9, "debug this")]
    pf = tmp_path / "learned_patterns.json"
    written = write_session_patterns(pf, events, files_edited=2, session_outcome="success")
    assert written == 0


def test_write_creates_file_with_patterns(tmp_path):
    events = [_prompt_event("debugging", 0.85, "TypeError in parser line 42")]
    pf = tmp_path / "learned_patterns.json"
    written = write_session_patterns(pf, events, files_edited=1, session_outcome="success")
    assert written == 1
    assert pf.exists()
    data = json.loads(pf.read_text())
    assert len(data["patterns"]) == 1
    assert data["patterns"][0]["domain"] == "debugging"
    assert data["patterns"][0]["weight"] == INITIAL_WEIGHT
    assert data["patterns"][0]["injection_count"] == 0
    assert data["patterns"][0]["utilization_successes"] == 0


def test_write_increments_on_repeated_success(tmp_path):
    events = [_prompt_event("debugging", 0.85, "TypeError in parser line 42")]
    pf = tmp_path / "learned_patterns.json"
    write_session_patterns(pf, events, files_edited=1, session_outcome="success")
    write_session_patterns(pf, events, files_edited=1, session_outcome="success")
    data = json.loads(pf.read_text())
    assert data["patterns"][0]["success_count"] == 2
    assert data["patterns"][0]["weight"] == round(INITIAL_WEIGHT + WEIGHT_INCREMENT, 3)


def test_write_increments_utilization_successes_when_pattern_injected(tmp_path):
    # First write: learn the pattern (no injected_pattern_ids)
    learn_events = [_prompt_event("debugging", 0.85, "TypeError in parser line 42")]
    pf = tmp_path / "learned_patterns.json"
    write_session_patterns(pf, learn_events, files_edited=1, session_outcome="success")
    pattern_id = json.loads(pf.read_text())["patterns"][0]["pattern_id"]

    # Second write: provide injected_pattern_ids to trigger metric update
    inject_events = [_prompt_event_with_pattern_ids(
        "debugging", 0.85, "TypeError in parser line 42", [pattern_id]
    )]
    write_session_patterns(pf, inject_events, files_edited=1, session_outcome="success")
    data = json.loads(pf.read_text())
    assert data["patterns"][0]["injection_count"] == 1
    assert data["patterns"][0]["utilization_successes"] == 1


def test_write_injected_success_patterns_gain_weight_faster(tmp_path):
    snippet = "TypeError in parser line 42"
    base_events = [_prompt_event("debugging", 0.85, snippet)]
    baseline_file = tmp_path / "baseline.json"

    # Baseline: two writes without injected_pattern_ids
    write_session_patterns(baseline_file, base_events, files_edited=1, session_outcome="success")
    write_session_patterns(baseline_file, base_events, files_edited=1, session_outcome="success")
    baseline_weight = json.loads(baseline_file.read_text())["patterns"][0]["weight"]

    # Injected: learn first, then inject the pattern_id on second write
    injected_file = tmp_path / "injected.json"
    write_session_patterns(injected_file, base_events, files_edited=1, session_outcome="success")
    pattern_id = json.loads(injected_file.read_text())["patterns"][0]["pattern_id"]
    inject_events = [_prompt_event_with_pattern_ids("debugging", 0.85, snippet, [pattern_id])]
    write_session_patterns(injected_file, inject_events, files_edited=1, session_outcome="success")
    injected_weight = json.loads(injected_file.read_text())["patterns"][0]["weight"]

    assert injected_weight > baseline_weight


def test_write_multiple_domains(tmp_path):
    events = [
        _prompt_event("debugging", 0.85, "TypeError in parser"),
        _prompt_event("brainstorming", 0.78, "brainstorm design options"),
    ]
    pf = tmp_path / "learned_patterns.json"
    written = write_session_patterns(pf, events, files_edited=2, session_outcome="success")
    assert written == 2
    data = json.loads(pf.read_text())
    domains = {p["domain"] for p in data["patterns"]}
    assert "debugging" in domains
    assert "brainstorming" in domains


# ---------------------------------------------------------------------------
# pattern_id helpers
# ---------------------------------------------------------------------------


def test_new_pattern_gets_deterministic_id(tmp_path):
    events = [_prompt_event("debugging", 0.85, "TypeError in parser line 42")]
    pf = tmp_path / "learned_patterns.json"
    write_session_patterns(pf, events, files_edited=1, session_outcome="success")
    data = json.loads(pf.read_text())
    pid = data["patterns"][0]["pattern_id"]
    assert pid.startswith("auto-")
    assert len(pid) == len("auto-") + 12


def test_same_domain_and_pattern_key_get_same_id():
    pid1 = _make_pattern_id("debugging", "line typeerror")
    pid2 = _make_pattern_id("debugging", "line typeerror")
    assert pid1 == pid2


def test_legacy_record_without_id_gets_backfilled(tmp_path):
    pf = tmp_path / "learned_patterns.json"
    pf.write_text(json.dumps({"patterns": [{
        "pattern": "line typeerror",
        "domain": "debugging",
        "weight": 0.7,
        "success_count": 2,
        "injection_count": 0,
        "utilization_successes": 0,
        "last_seen": time.time(),
        "description": "legacy",
    }]}))
    # Any write causes _load_patterns to backfill
    write_session_patterns(pf, [], files_edited=0, session_outcome="success")
    data = json.loads(pf.read_text())
    pid = data["patterns"][0].get("pattern_id", "")
    assert pid.startswith("auto-") and len(pid) == 17


def test_existing_seed_pattern_id_is_preserved(tmp_path):
    pf = tmp_path / "learned_patterns.json"
    pf.write_text(json.dumps({"patterns": [{
        "pattern_id": "seed-s1-fixed",
        "pattern": "git bisect",
        "domain": "general",
        "weight": 0.75,
        "success_count": 1,
        "injection_count": 0,
        "utilization_successes": 0,
        "last_seen": time.time(),
        "description": "seed",
    }]}))
    # Load triggers backfill — but existing ID must not be overwritten
    write_session_patterns(pf, [], files_edited=0, session_outcome="success")
    data = json.loads(pf.read_text())
    assert data["patterns"][0]["pattern_id"] == "seed-s1-fixed"


# ---------------------------------------------------------------------------
# Outcome semantics via injected_pattern_ids
# ---------------------------------------------------------------------------


def _make_pf_with_known_id(tmp_path, pattern_id: str, injection_count: int = 0,
                            utilization_successes: int = 0, weight: float = 0.7):
    pf = tmp_path / "learned_patterns.json"
    pf.write_text(json.dumps({"patterns": [{
        "pattern_id": pattern_id,
        "pattern": "some pattern",
        "domain": "debugging",
        "weight": weight,
        "success_count": 2,
        "injection_count": injection_count,
        "utilization_successes": utilization_successes,
        "last_seen": time.time(),
        "description": "test pattern",
    }]}))
    return pf


def test_failed_outcome_increments_injection_count_only(tmp_path):
    pid = "auto-aabbcc112233"
    pf = _make_pf_with_known_id(tmp_path, pid, weight=0.7)
    events = [_prompt_event_with_pattern_ids("debugging", 0.85, "TypeError", [pid])]
    write_session_patterns(pf, events, files_edited=1, session_outcome="failed")
    data = json.loads(pf.read_text())["patterns"][0]
    assert data["injection_count"] == 1
    assert data["utilization_successes"] == 0
    assert data["weight"] == 0.7  # unchanged


def test_abandoned_outcome_increments_injection_count_only(tmp_path):
    pid = "auto-aabbcc112233"
    pf = _make_pf_with_known_id(tmp_path, pid, weight=0.7)
    events = [_prompt_event_with_pattern_ids("debugging", 0.85, "TypeError", [pid])]
    write_session_patterns(pf, events, files_edited=1, session_outcome="abandoned")
    data = json.loads(pf.read_text())["patterns"][0]
    assert data["injection_count"] == 1
    assert data["utilization_successes"] == 0
    assert data["weight"] == 0.7


def test_unknown_outcome_increments_injection_count_only(tmp_path):
    pid = "auto-aabbcc112233"
    pf = _make_pf_with_known_id(tmp_path, pid, weight=0.7)
    events = [_prompt_event_with_pattern_ids("debugging", 0.85, "TypeError", [pid])]
    write_session_patterns(pf, events, files_edited=1, session_outcome="unknown")
    data = json.loads(pf.read_text())["patterns"][0]
    assert data["injection_count"] == 1
    assert data["utilization_successes"] == 0
    assert data["weight"] == 0.7


def test_success_outcome_with_injected_id_increments_injection_and_utilization(tmp_path):
    pid = "auto-aabbcc112233"
    pf = _make_pf_with_known_id(tmp_path, pid, weight=0.7)
    events = [_prompt_event_with_pattern_ids("debugging", 0.85, "TypeError", [pid])]
    write_session_patterns(pf, events, files_edited=1, session_outcome="success")
    data = json.loads(pf.read_text())["patterns"][0]
    assert data["injection_count"] == 1
    assert data["utilization_successes"] == 1
    assert data["weight"] > 0.7  # bumped by multiplier


def test_failed_outcome_does_not_create_new_patterns_from_snippet(tmp_path):
    events = [_prompt_event("debugging", 0.85, "TypeError in parser line 42")]
    pf = tmp_path / "learned_patterns.json"
    written = write_session_patterns(pf, events, files_edited=2, session_outcome="failed")
    assert written == 0
    assert not pf.exists()


def test_success_with_zero_files_edited_updates_metrics_but_does_not_learn(tmp_path):
    pid = "auto-aabbcc112233"
    pf = _make_pf_with_known_id(tmp_path, pid)
    initial_count = len(json.loads(pf.read_text())["patterns"])
    events = [_prompt_event_with_pattern_ids("debugging", 0.85, "TypeError", [pid])]
    write_session_patterns(pf, events, files_edited=0, session_outcome="success")
    data = json.loads(pf.read_text())
    assert len(data["patterns"]) == initial_count  # no new pattern learned
    assert data["patterns"][0]["injection_count"] == 1
    assert data["patterns"][0]["utilization_successes"] == 1


def test_unknown_injected_id_is_skipped_silently(tmp_path):
    pf = tmp_path / "learned_patterns.json"
    events = [_prompt_event_with_pattern_ids("debugging", 0.85, "TypeError", ["auto-nonexistent0"])]
    written = write_session_patterns(pf, events, files_edited=0, session_outcome="failed")
    assert written == 0
    assert not pf.exists()


def test_missing_injected_pattern_ids_field_does_not_crash(tmp_path):
    events = [_prompt_event("debugging", 0.85, "TypeError")]
    pf = tmp_path / "learned_patterns.json"
    written = write_session_patterns(pf, events, files_edited=1, session_outcome="success")
    assert written >= 0  # no crash


def test_duplicate_ids_within_event_counted_once(tmp_path):
    pid = "auto-aabbcc112233"
    pf = _make_pf_with_known_id(tmp_path, pid)
    events = [_prompt_event_with_pattern_ids("debugging", 0.85, "TypeError", [pid, pid])]
    write_session_patterns(pf, events, files_edited=0, session_outcome="failed")
    data = json.loads(pf.read_text())["patterns"][0]
    assert data["injection_count"] == 1  # deduplicated within event


def test_same_id_across_two_events_counted_twice(tmp_path):
    pid = "auto-aabbcc112233"
    pf = _make_pf_with_known_id(tmp_path, pid)
    events = [
        _prompt_event_with_pattern_ids("debugging", 0.85, "TypeError A", [pid]),
        _prompt_event_with_pattern_ids("debugging", 0.85, "TypeError B", [pid]),
    ]
    write_session_patterns(pf, events, files_edited=0, session_outcome="failed")
    data = json.loads(pf.read_text())["patterns"][0]
    assert data["injection_count"] == 2  # counted once per event


# ---------------------------------------------------------------------------
# Atomic write
# ---------------------------------------------------------------------------


def test_atomic_write_uses_replace(tmp_path, monkeypatch):
    replace_calls = []
    real_replace = __import__("os").replace

    def mock_replace(src, dst):
        replace_calls.append((src, dst))
        return real_replace(src, dst)

    import omnicursor.pattern_writer as _pw
    monkeypatch.setattr(_pw.os, "replace", mock_replace)
    events = [_prompt_event("debugging", 0.85, "TypeError in parser")]
    pf = tmp_path / "learned_patterns.json"
    write_session_patterns(pf, events, files_edited=1, session_outcome="success")
    assert len(replace_calls) == 1
    src, dst = replace_calls[0]
    assert str(dst) == str(pf)
    assert src != dst


def test_atomic_write_cleans_up_tmp_on_failure(tmp_path, monkeypatch):
    import omnicursor.pattern_writer as _pw

    def failing_replace(src, dst):
        raise OSError("simulated disk full")

    monkeypatch.setattr(_pw.os, "replace", failing_replace)
    events = [_prompt_event("debugging", 0.85, "TypeError in parser")]
    pf = tmp_path / "learned_patterns.json"
    # Should not crash (outer try/except) and no tmp file should remain
    write_session_patterns(pf, events, files_edited=1, session_outcome="success")
    tmp_files = list(tmp_path.glob("*.tmp"))
    assert tmp_files == []


# ---------------------------------------------------------------------------
# Eviction after failed injections
# ---------------------------------------------------------------------------


def test_low_utilization_pattern_is_evicted_after_failed_injections(tmp_path):
    pid = "auto-evict00112233"
    # Pattern already at eviction threshold: injection_count=EVICT_MIN, 0 successes
    pf = _make_pf_with_known_id(
        tmp_path, pid,
        injection_count=UTILIZATION_EVICT_MIN_INJECTIONS,
        utilization_successes=0,
        weight=0.7,
    )
    events = [_prompt_event_with_pattern_ids("debugging", 0.85, "TypeError", [pid])]
    # One more failed injection pushes injection_count over the threshold
    write_session_patterns(pf, events, files_edited=0, session_outcome="failed")
    data = json.loads(pf.read_text())
    remaining_ids = [p["pattern_id"] for p in data["patterns"]]
    assert pid not in remaining_ids
