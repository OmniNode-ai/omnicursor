#!/usr/bin/env python3
"""Routing accuracy eval harness.

Loads routing_labeled_prompts.csv, runs each prompt through the three-strategy
scorer against all agent configs, and reports per-agent precision/recall/F1 plus
overall accuracy.

Usage:
    cd <repo-root>
    python eval/eval_routing.py

Output:
    - Console: per-agent table + summary
    - eval/routing_results.csv: full per-prompt results for the repo
"""
from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent
AGENTS_DIR = REPO_ROOT / "agents"
PROMPTS_CSV = Path(__file__).parent / "routing_labeled_prompts.csv"
RESULTS_CSV = Path(__file__).parent / "routing_results.csv"

sys.path.insert(0, str(REPO_ROOT / "src"))
from omnicursor.scoring import HARD_FLOOR, extract_keywords, score_agent  # noqa: E402


def classify_prompt(prompt: str, agents: list[dict]) -> tuple[str, float, str]:
    if not prompt or not agents:
        return ("polymorphic-agent", 0.0, "No agent matched")

    prompt_lower = prompt.lower()
    prompt_words = set(extract_keywords(prompt))
    best_name, best_score, best_reason = "polymorphic-agent", 0.0, "No agent matched"

    for agent in agents:
        name = agent.get("name", "")
        if not name:
            continue
        sc, reason = score_agent(prompt_lower, prompt_words, agent)
        if sc >= HARD_FLOOR and sc > best_score:
            best_score, best_name, best_reason = sc, name, reason

    return (best_name, best_score, best_reason)


# ---------------------------------------------------------------------------
# Load agents
# ---------------------------------------------------------------------------

def load_agents() -> list[dict]:
    agents = []
    for path in sorted(AGENTS_DIR.glob("*.json")):
        try:
            agents.append(json.loads(path.read_text()))
        except Exception as e:
            print(f"Warning: could not load {path.name}: {e}", file=sys.stderr)
    return agents


# ---------------------------------------------------------------------------
# Load labeled prompts
# ---------------------------------------------------------------------------

def load_prompts() -> list[dict]:
    prompts = []
    with open(PROMPTS_CSV, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            text = row["prompt_text"].strip().strip('"')
            prompts.append({
                "prompt": text,
                "expected": row["expected_agent"].strip(),
                "notes": row.get("notes", "").strip(),
            })
    return prompts


# ---------------------------------------------------------------------------
# Eval
# ---------------------------------------------------------------------------

def run_eval(agents: list[dict], prompts: list[dict]) -> list[dict]:
    results = []
    for p in prompts:
        predicted, score, reason = classify_prompt(p["prompt"], agents)
        correct = predicted == p["expected"]
        results.append({
            "prompt": p["prompt"],
            "expected": p["expected"],
            "predicted": predicted,
            "score": round(score, 4),
            "correct": correct,
            "reason": reason,
            "notes": p["notes"],
        })
    return results


def compute_metrics(results: list[dict]) -> dict:
    agents_seen = {r["expected"] for r in results} | {r["predicted"] for r in results}
    tp: dict[str, int] = defaultdict(int)
    fp: dict[str, int] = defaultdict(int)
    fn: dict[str, int] = defaultdict(int)

    for r in results:
        exp, pred = r["expected"], r["predicted"]
        if pred == exp:
            tp[exp] += 1
        else:
            fp[pred] += 1
            fn[exp] += 1

    metrics = {}
    for agent in sorted(agents_seen):
        p = tp[agent] / (tp[agent] + fp[agent]) if (tp[agent] + fp[agent]) > 0 else 0.0
        r = tp[agent] / (tp[agent] + fn[agent]) if (tp[agent] + fn[agent]) > 0 else 0.0
        f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
        support = tp[agent] + fn[agent]
        metrics[agent] = {"precision": p, "recall": r, "f1": f1, "support": support, "tp": tp[agent]}

    return metrics


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_report(results: list[dict], metrics: dict) -> None:
    total = len(results)
    correct = sum(1 for r in results if r["correct"])
    accuracy = correct / total if total else 0.0

    print(f"\n{'='*72}")
    print(f"  OmniCursor Routing Eval — {total} prompts")
    print(f"{'='*72}")
    print(f"  Overall accuracy: {correct}/{total} = {accuracy:.1%}")
    print()

    header = f"  {'Agent':<28} {'Prec':>6} {'Rec':>6} {'F1':>6} {'Support':>8}"
    print(header)
    print("  " + "-" * 60)

    target_agents = [
        "address-pr-comments", "code-quality-analyzer", "commit",
        "content-summarizer", "debug-database", "debug-intelligence",
        "documentation-architect", "frontend-developer", "handoff",
        "performance", "polymorphic-agent", "pr-review",
        "python-fastapi-expert", "repository-crawler", "research",
        "security-audit", "testing",
    ]

    macro_p, macro_r, macro_f1, n_agents = 0.0, 0.0, 0.0, 0
    for agent in target_agents:
        if agent not in metrics:
            continue
        m = metrics[agent]
        flag = "" if m["recall"] >= 0.60 and m["precision"] >= 0.80 else " <"
        print(f"  {agent:<28} {m['precision']:>5.0%} {m['recall']:>5.0%} {m['f1']:>5.0%} {m['support']:>8}{flag}")
        macro_p += m["precision"]
        macro_r += m["recall"]
        macro_f1 += m["f1"]
        n_agents += 1

    print("  " + "-" * 60)
    if n_agents:
        print(f"  {'Macro avg':<28} {macro_p/n_agents:>5.0%} {macro_r/n_agents:>5.0%} {macro_f1/n_agents:>5.0%}")

    print()
    target_p = macro_p / n_agents if n_agents else 0
    target_r = macro_r / n_agents if n_agents else 0
    bar_p = "PASS" if target_p >= 0.80 else "FAIL"
    bar_r = "PASS" if target_r >= 0.60 else "FAIL"
    print(f"  Precision ≥ 0.80: {bar_p} ({target_p:.1%})")
    print(f"  Recall    ≥ 0.60: {bar_r} ({target_r:.1%})")
    print(f"{'='*72}\n")

    wrong = [r for r in results if not r["correct"]]
    if wrong:
        print(f"  Misclassified ({len(wrong)}):")
        for r in wrong:
            print(f"    expected={r['expected']:<28} predicted={r['predicted']:<28} score={r['score']:.2f}")
            print(f"      prompt: {r['prompt'][:70]}")
        print()


def write_results_csv(results: list[dict]) -> None:
    with open(RESULTS_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["prompt", "expected", "predicted", "correct", "score", "reason", "notes"])
        writer.writeheader()
        writer.writerows(results)
    print(f"  Results written to: {RESULTS_CSV.relative_to(REPO_ROOT)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    agents = load_agents()
    if not agents:
        print(f"Error: no agent JSONs found in {AGENTS_DIR}", file=sys.stderr)
        sys.exit(1)

    prompts = load_prompts()
    if not prompts:
        print(f"Error: no prompts found in {PROMPTS_CSV}", file=sys.stderr)
        sys.exit(1)

    results = run_eval(agents, prompts)
    metrics = compute_metrics(results)
    print_report(results, metrics)
    write_results_csv(results)
