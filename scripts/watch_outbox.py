#!/usr/bin/env python3
"""Watch ~/.omnicursor/outbox.jsonl and pretty-print new entries as they arrive."""
import json
import pathlib
import sys
import time

OUTBOX = pathlib.Path.home() / ".omnicursor" / "outbox.jsonl"

RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
CYAN   = "\033[36m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
RED    = "\033[31m"
BLUE   = "\033[34m"
MAGENTA = "\033[35m"

OUTCOME_COLORS = {
    "success":   GREEN,
    "failed":    RED,
    "abandoned": YELLOW,
    "unknown":   DIM,
}

EVENT_COLORS = {
    "session.outcome":                GREEN,
    "utilization.scoring.requested":  CYAN,
    "onex.cmd.omnicursor.cursor-hook-event.v1": BLUE,
}


def _color_outcome(outcome: str) -> str:
    c = OUTCOME_COLORS.get(outcome, RESET)
    return f"{c}{BOLD}{outcome.upper()}{RESET}"


def _fmt_session(row: dict) -> str:
    conv = row.get("conversation_id", "")[:8]
    outcome = row.get("session_outcome", "?")
    agent = row.get("matched_agent") or "—"
    conf = row.get("matched_confidence")
    conf_str = f"{conf:.2f}" if conf is not None else "—"
    files = row.get("files_edited", 0)
    prompts = row.get("prompts_classified", 0)
    patterns = row.get("patterns_injected", 0)
    reason = row.get("session_outcome_reason", "")

    lines = [
        f"{BOLD}{CYAN}── SESSION OUTCOME{RESET}  {DIM}conv={conv}…{RESET}",
        f"  outcome  : {_color_outcome(outcome)}",
        f"  agent    : {MAGENTA}{agent}{RESET}  conf={conf_str}",
        f"  prompts  : {prompts}   files edited: {files}   patterns injected: {patterns}",
        f"  reason   : {DIM}{reason}{RESET}",
    ]
    pids = row.get("injected_pattern_ids", [])
    if pids:
        lines.append(f"  patterns : {DIM}{', '.join(pids)}{RESET}")
    return "\n".join(lines)


def _fmt_socket_event(row: dict) -> str:
    etype = row.get("event_type", "?")
    payload = row.get("payload", {})
    color = EVENT_COLORS.get(etype, RESET)

    if etype == "session.outcome":
        outcome = payload.get("outcome", "?")
        agent = payload.get("matched_agent") or "—"
        sid = payload.get("session_id", "")[:8]
        lines = [
            f"{BOLD}{color}── SOCKET EVENT  session.outcome{RESET}  {DIM}session={sid}…{RESET}",
            f"  outcome  : {_color_outcome(outcome)}",
            f"  agent    : {MAGENTA}{agent}{RESET}",
        ]
    elif etype == "utilization.scoring.requested":
        sid = payload.get("session_id", "")[:8]
        pids = payload.get("injected_pattern_ids", [])
        lines = [
            f"{BOLD}{color}── SOCKET EVENT  utilization.scoring.requested{RESET}  {DIM}session={sid}…{RESET}",
            f"  patterns : {DIM}{', '.join(pids) if pids else '—'}{RESET}",
        ]
    elif "cursor-hook-event" in etype:
        hook = payload.get("hook", "?")
        agent = payload.get("matched_agent") or "—"
        score = payload.get("score", 0.0)
        conv = payload.get("conversation_id", "")[:8]
        lines = [
            f"{BOLD}{color}── HOOK  {hook}{RESET}  {DIM}conv={conv}…{RESET}",
            f"  agent    : {MAGENTA}{agent}{RESET}  score={score:.2f}",
        ]
    else:
        lines = [
            f"{BOLD}{color}── EVENT  {etype}{RESET}",
            f"  {DIM}{json.dumps(payload, separators=(',', ':'))[:120]}{RESET}",
        ]

    return "\n".join(lines)


def _fmt_row(line: str) -> str:
    try:
        row = json.loads(line)
    except json.JSONDecodeError:
        return f"{DIM}{line.strip()}{RESET}"

    if "schema_version" in row:
        return _fmt_session(row)
    if "event_type" in row:
        return _fmt_socket_event(row)
    return f"{DIM}{line.strip()}{RESET}"


def main() -> None:
    path = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else OUTBOX
    if not path.exists():
        print(f"{YELLOW}Waiting for {path} to be created…{RESET}")
        while not path.exists():
            time.sleep(0.5)

    print(f"{DIM}Watching {path} — new entries will appear below{RESET}\n")

    with path.open("r", encoding="utf-8") as f:
        f.seek(0, 2)  # seek to end — only show new lines
        while True:
            line = f.readline()
            if line:
                formatted = _fmt_row(line)
                print(formatted)
                print()
            else:
                time.sleep(0.3)


if __name__ == "__main__":
    main()
