"""Discover and validate OmniCursor node contracts (OmniClaude-parity, Cursor-native).

Contracts live under ``omnicursor/nodes/*/contract.yaml``. They describe integration
surfaces analogous to OmniClaude ``contract.yaml`` nodes, but **execution** is always
via Cursor (``hooks.json`` + ``.cursor/hooks/*.py``), not Kafka.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator

import yaml
from pydantic import BaseModel, ConfigDict, Field


class VersionTriple(BaseModel):
    model_config = ConfigDict(extra="ignore")

    major: int = 0
    minor: int = 0
    patch: int = 0


class CursorNativeSpec(BaseModel):
    """How this node binds to Cursor IDE hooks (source of truth: ``.cursor/hooks.json``)."""

    model_config = ConfigDict(extra="ignore")

    hook_event: str = Field(
        ..., description="Cursor hook name, e.g. beforeSubmitPrompt"
    )
    hooks_json_command: str = Field(
        ...,
        description="Command string as registered in hooks.json",
    )
    implementation: str = Field(
        ...,
        description="Repo-relative path to the stdlib-only hook script",
    )
    blocking: bool = Field(
        False,
        description="Whether the hook can deny/block the underlying action",
    )


class OmniCursorNodeContract(BaseModel):
    """Subset of OmniClaude contract fields + Cursor-specific binding."""

    model_config = ConfigDict(extra="allow")

    name: str
    contract_name: str | None = None
    node_name: str | None = None
    contract_version: VersionTriple | None = None
    node_version: VersionTriple | None = None
    node_type: str
    description: str = ""
    cursor_native: CursorNativeSpec
    execution: dict[str, Any] | None = None
    local_event_bus: dict[str, Any] | None = Field(
        None,
        description="Optional: append-only log / local bus (replaces Kafka in OmniClaude)",
    )


def contracts_root() -> Path:
    """Directory containing ``node_*/contract.yaml``."""
    return Path(__file__).resolve().parent / "nodes"


def iter_contract_paths(root: Path | None = None) -> Iterator[Path]:
    base = root if root is not None else contracts_root()
    if not base.is_dir():
        return
    yield from sorted(base.glob("*/contract.yaml"))


def load_contract(path: Path) -> OmniCursorNodeContract:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = f"Contract must be a mapping: {path}"
        raise ValueError(msg)
    return OmniCursorNodeContract.model_validate(raw)


@lru_cache(maxsize=1)
def load_all_contracts(root: Path | None = None) -> tuple[OmniCursorNodeContract, ...]:
    """Parse every ``contract.yaml`` under ``nodes/`` (cached)."""
    paths = list(iter_contract_paths(root))
    return tuple(load_contract(p) for p in paths)


def hooks_registration_ok(
    contracts: tuple[OmniCursorNodeContract, ...] | None = None,
) -> bool:
    """Best-effort check that declared hook commands match hooks.json entries.

    Does not execute hooks — only compares ``hooks_json_command`` strings to the
    project ``.cursor/hooks.json`` file, relative to the OmniCursor repo root.
    """
    import json

    if contracts is None:
        contracts = load_all_contracts()

    repo_root = Path(__file__).resolve().parents[2]
    hooks_path = repo_root / ".cursor" / "hooks.json"
    if not hooks_path.is_file():
        return False

    registered: dict[str, Any] = json.loads(hooks_path.read_text(encoding="utf-8"))
    hook_map: dict[str, list[dict[str, str]]] = registered.get("hooks", {})
    for c in contracts:
        event = c.cursor_native.hook_event
        cmd = c.cursor_native.hooks_json_command
        cmds = [entry.get("command", "") for entry in hook_map.get(event, [])]
        if cmd not in cmds:
            return False
    return True
