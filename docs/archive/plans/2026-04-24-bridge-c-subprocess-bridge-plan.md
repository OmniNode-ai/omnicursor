# BRIDGE-C: Subprocess Bridge to Omnimarket `node_local_review`

**Date:** 2026-04-24
**Source:** Sponsor alignment (2026-04-16), BRIDGE-B conventions (OMNIMARKET_ROOT)
**Status:** Preflight approved, not yet executed

---

## Design

One module: `src/omnicursor/omnimarket_bridge.py`. One public function: `run_local_review()`.

### Resolution order for Omnimarket root

1. `OMNIMARKET_ROOT` env var (absolute path to local checkout).
2. `omnimarket-main/` in repo root (dev fallback — detected via `Path(__file__).resolve()` walking up to find `.git`).
3. Neither exists → return structured error with setup instructions.

### Resolution for Python executable

1. `OMNIMARKET_PYTHON` env var (e.g. path to a venv `python` inside the omnimarket checkout).
2. Fallback: `sys.executable`.

### Subprocess invocation

```python
subprocess.run(
    [python, "-m", "omnimarket.nodes.node_local_review", ...args],
    cwd=omnimarket_root,
    capture_output=True,
    text=True,
    timeout=300,
)
```

CLI args built from function parameters:
- `--dry-run` if `dry_run=True`
- `--max-iterations N` if `max_iterations` is not None
- `--required-clean-runs N` if `required_clean_runs` is not None

### Return type

A `TypedDict` called `BridgeResult`:

```python
class BridgeResult(TypedDict):
    ok: bool
    returncode: int
    state: dict | None      # parsed stdout JSON, or None on parse failure
    stderr: str
    error: str | None        # human-readable error if ok=False
```

### Failure behavior

| Scenario | `ok` | `state` | `error` |
|----------|------|---------|---------|
| Omnimarket root not found | `False` | `None` | Setup instructions naming `OMNIMARKET_ROOT` |
| Python executable not found | `False` | `None` | Names the path that was tried |
| Subprocess returncode != 0 | `False` | parsed if possible | stderr content |
| Subprocess timeout | `False` | `None` | Timeout message with duration |
| stdout not valid JSON | `False` | `None` | Parse error + raw stdout snippet |
| Success (rc=0, valid JSON) | `True` | parsed dict | `None` |

No exceptions raised to callers. All failures are expressed in the return dict.

---

## Files

| Action | Path | Notes |
|--------|------|-------|
| **Add** | `src/omnicursor/omnimarket_bridge.py` | Bridge module (~80 lines) |
| **Add** | `tests/test_omnimarket_bridge.py` | Unit tests with subprocess mocking (~120 lines) |

No other files edited. No schema changes (uses `TypedDict`, not Pydantic — the bridge is a thin subprocess wrapper, not a domain model).

---

## Test plan

All tests mock `subprocess.run` via `monkeypatch.setattr` (repo convention). No real Omnimarket execution.

| Test | What it verifies |
|------|-----------------|
| `test_success_parses_json` | rc=0 + valid JSON → `ok=True`, `state` populated |
| `test_dry_run_flag` | `dry_run=True` → `--dry-run` in command args |
| `test_max_iterations_flag` | `max_iterations=5` → `--max-iterations 5` in args |
| `test_required_clean_runs_flag` | `required_clean_runs=3` → `--required-clean-runs 3` in args |
| `test_all_defaults` | No optional args → no CLI flags beyond module path |
| `test_missing_root_returns_error` | Neither env var nor fallback dir exists → `ok=False`, error names `OMNIMARKET_ROOT` |
| `test_env_root_takes_priority` | `OMNIMARKET_ROOT` set + fallback exists → uses env var path |
| `test_fallback_to_repo_local` | No env var, `omnimarket-main/` exists → uses it |
| `test_nonzero_returncode` | rc=1 → `ok=False`, stderr captured |
| `test_invalid_json_stdout` | rc=0 but stdout not JSON → `ok=False`, error describes parse failure |
| `test_timeout` | `subprocess.TimeoutExpired` raised → `ok=False`, timeout error |
| `test_custom_python_env` | `OMNIMARKET_PYTHON` set → used as executable |
| `test_cwd_is_omnimarket_root` | Subprocess `cwd` kwarg matches resolved root |

---

## Verification (post-implementation)

```bash
ruff check src/omnicursor/omnimarket_bridge.py tests/test_omnimarket_bridge.py
pytest tests/test_omnimarket_bridge.py -v
pytest tests/ -v  # full suite, no regressions
```

---

## Out of scope

- MCP tool wrapping this function (BRIDGE-D)
- In-process handler import fallback
- `onex run` integration
- Direct omniintelligence HTTP calls
- Docker Compose changes
- Schema/model additions to `schemas.py`
