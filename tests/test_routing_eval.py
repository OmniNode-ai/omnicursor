# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Routing accuracy gate — enforces precision ≥ 0.80 and recall ≥ 0.60.

Loads eval/routing_labeled_prompts.csv and runs the three-strategy scorer
against all agent configs. Fails CI if macro averages drop below the v1 bar.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent
AGENTS_DIR = REPO_ROOT / ".cursor" / "agents"
PROMPTS_CSV = REPO_ROOT / "eval" / "routing_labeled_prompts.csv"

# ---------------------------------------------------------------------------
# Import the canonical scorer
# ---------------------------------------------------------------------------

sys.path.insert(0, str(REPO_ROOT / "src"))
from omnicursor.scoring import HARD_FLOOR, extract_keywords, score_agent  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_agents() -> list[dict]:
    agents = []
    for path in sorted(AGENTS_DIR.glob("*.json")):
        agents.append(json.loads(path.read_text()))
    return agents


def _load_prompts() -> list[dict]:
    rows = []
    with open(PROMPTS_CSV, newline="") as f:
        for row in csv.DictReader(f):
            rows.append(
                {
                    "prompt": row["prompt_text"].strip().strip('"'),
                    "expected": row["expected_agent"].strip(),
                }
            )
    return rows


def _classify(prompt: str, agents: list[dict]) -> tuple[str, float]:
    if not prompt or not agents:
        return ("polymorphic-agent", 0.0)
    prompt_lower = prompt.lower()
    prompt_words = set(extract_keywords(prompt))
    best_name, best_score = "polymorphic-agent", 0.0
    for agent in agents:
        name = agent.get("name", "")
        if not name:
            continue
        sc, _ = score_agent(prompt_lower, prompt_words, agent)
        if sc >= HARD_FLOOR and sc > best_score:
            best_score, best_name = sc, name
    return (best_name, best_score)


def _compute_macro(results: list[dict]) -> tuple[float, float]:
    tp: dict[str, int] = defaultdict(int)
    fp: dict[str, int] = defaultdict(int)
    fn: dict[str, int] = defaultdict(int)
    for r in results:
        if r["predicted"] == r["expected"]:
            tp[r["expected"]] += 1
        else:
            fp[r["predicted"]] += 1
            fn[r["expected"]] += 1
    agents = {r["expected"] for r in results}
    precisions, recalls = [], []
    for a in agents:
        denom_p = tp[a] + fp[a]
        denom_r = tp[a] + fn[a]
        precisions.append(tp[a] / denom_p if denom_p else 0.0)
        recalls.append(tp[a] / denom_r if denom_r else 0.0)
    return (
        sum(precisions) / len(precisions) if precisions else 0.0,
        sum(recalls) / len(recalls) if recalls else 0.0,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def eval_results() -> list[dict]:
    agents = _load_agents()
    prompts = _load_prompts()
    results = []
    for p in prompts:
        predicted, score = _classify(p["prompt"], agents)
        results.append(
            {"expected": p["expected"], "predicted": predicted, "score": score}
        )
    return results


def test_routing_prompt_count(eval_results: list[dict]) -> None:
    assert len(eval_results) >= 100, (
        f"Expected ≥100 labeled prompts, got {len(eval_results)}"
    )


def test_routing_macro_precision(eval_results: list[dict]) -> None:
    macro_p, _ = _compute_macro(eval_results)
    assert macro_p >= 0.80, (
        f"Macro precision {macro_p:.1%} below v1 bar of 80%. "
        "Run eval/eval_routing.py for the per-agent breakdown."
    )


def test_routing_macro_recall(eval_results: list[dict]) -> None:
    _, macro_r = _compute_macro(eval_results)
    assert macro_r >= 0.60, (
        f"Macro recall {macro_r:.1%} below v1 bar of 60%. "
        "Run eval/eval_routing.py for the per-agent breakdown."
    )
