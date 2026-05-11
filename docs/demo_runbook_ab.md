# OmniCursor Demo Runbook — Option A + Option B mínima

**Fecha:** 2026-05-09  
**Rama:** `julian/option-b-from-main`  
**Suite:** 598 tests verdes, ruff limpio

---

## Goal

Demostrar que OmniCursor tiene una **intelligence layer local-first** completamente funcional sin infraestructura externa. La demo prueba 5 escenarios reales y ejecutables:

1. **Auto-routing** — el hook `beforeSubmitPrompt` clasifica el prompt y elige un agente automáticamente, sin llamar MCP explícitamente.
2. **Auto-lint** — el hook `afterFileEdit` corre `ruff check` sobre archivos Python editados y emite los findings al log.
3. **Pattern persistence** — `learned_patterns.json` persiste patterns entre sesiones; la siguiente sesión los inyecta en el sistema message.
4. **Durable outbox** — al terminar cada sesión, `stop.py` escribe un payload estructurado a `~/.omnicursor/outbox.jsonl` (schema `omnicursor.session_outcome.v1`), el contrato que Option C drenará a Kafka.
5. **MCP fallback** — con hooks deshabilitados, el bridge Omnimarket sigue disponible vía MCP, demostrando que la arquitectura no depende de un único punto de fallo.

**Docker: NO requerido.** La historia central es "local-first, sin infraestructura". Docker es solo para un smoke opcional de Option C readiness al final.

---

## Demo Narrative

> *"OmniCursor convierte Cursor en un agente con memoria local persistente y un bridge preparado para OmniIntelligence. Cada prompt es clasificado automáticamente. Cada edit pasa por un lint gate. Los patrones aprendidos cruzan sesiones. Y cuando cerrás la sesión, el outcome queda en un outbox durable listo para ser drenado upstream. Todo esto sin Docker, sin Kafka, sin servicios externos."*

---

## Preconditions

| Ítem | Valor |
|------|-------|
| Repo | `/Users/jirustaroure/Desktop/OmniCursor` |
| Rama | `julian/option-b-from-main` |
| Python venv | `.venv` (Python 3.12) |
| `ruff` | disponible en `.venv/bin/ruff` |
| `jq` | recomendado para evidencia legible |
| `watch` | opcional para panel de learned_patterns en vivo |
| Docker | NO requerido para A+B |
| Omnimarket checkout | `/Users/jirustaroure/Desktop/OmniCursor/omnimarket` |
| Omnimarket SHA | `ce0f3bec8a049bb9ae728adee2d053fd4cebe28b` (branch `main`) |
| `.cursor/mcp.json` | `OMNIMARKET_ROOT` apunta al checkout |

---

## Safety Setup

**Hacer esto antes de la demo. Documentado — ejecutar manualmente.**

```bash
# Backup de los archivos de estado
mkdir -p ~/.omnicursor/demo-backup
cp ~/.omnicursor/events.jsonl ~/.omnicursor/demo-backup/events.$(date +%Y%m%d%H%M%S).jsonl 2>/dev/null || true
cp ~/.omnicursor/outbox.jsonl ~/.omnicursor/demo-backup/outbox.$(date +%Y%m%d%H%M%S).jsonl 2>/dev/null || true
cp ~/.omnicursor/learned_patterns.json ~/.omnicursor/demo-backup/learned_patterns.$(date +%Y%m%d%H%M%S).json 2>/dev/null || true
```

> **Nota:** Para una demo limpia de outbox, conviene usar `OMNICURSOR_OUTBOX_FILE=~/.omnicursor/demo-outbox.jsonl` como variable de entorno en el shell donde corras Cursor. Así el outbox de la demo queda separado del histórico de tests.
>
> `learned_patterns.json` es el read cache canónico de Option A. Si se pre-seedea (ver Escenario 3), hacerlo siempre con backup previo.

---

## Verification Commands

Correr antes de grabar/presentar:

```bash
# 1. Suite completa
.venv/bin/python -m pytest -q
# Esperado: 598 passed en ~1.2s

# 2. Lint
.venv/bin/python -m ruff check src/ tests/ .cursor/hooks/
# Esperado: All checks passed!

# 3. Bridge smoke (shell directo)
OMNIMARKET_ROOT=/Users/jirustaroure/Desktop/OmniCursor/omnimarket \
  .venv/bin/python -c "
import json
from omnicursor.omnimarket_bridge import run_local_review
print(json.dumps(run_local_review(dry_run=True), indent=2, default=str))
"
# Esperado: "ok": true
```

---

## Live Evidence Windows

Abrir **3 terminales** antes de empezar:

**Terminal 1 — Events en tiempo real:**
```bash
tail -f ~/.omnicursor/events.jsonl | jq 'select(
  .event=="prompt_classified" or
  .event=="file_edited" or
  .event=="session_stopped"
)'
```

**Terminal 2 — Outbox en tiempo real:**
```bash
tail -f ~/.omnicursor/outbox.jsonl | jq .
# Si usás env override: tail -f ~/.omnicursor/demo-outbox.jsonl | jq .
```

**Terminal 3 — Learned patterns (panel estático):**
```bash
watch -n 2 'jq "{count: (.patterns|length), last_seen: .patterns[-1].pattern_id, top5_weight: [.patterns | sort_by(-.weight) | .[:5] | .[].pattern_id]}" ~/.omnicursor/learned_patterns.json 2>/dev/null || echo "no patterns yet"'
```

---

## Scenario 1 — Prompt Auto-Routing

**Qué demostrar:** el hook `beforeSubmitPrompt` clasifica el prompt entrante con tres estrategias (substring match → fuzzy match → keyword overlap) y elige un agente con confidence ≥ 0.55. Esto ocurre sin llamar MCP.

**Prompt para Cursor:**
```
Debug why pattern_sync should never overwrite learned_patterns.json when omniintelligence is offline. Inspect the current implementation and list the evidence. Do not edit files. Finish with the word done.
```

**Evidencia esperada en Terminal 1:**
```json
{
  "event": "prompt_classified",
  "matched_agent": "debug-intelligence",
  "score": 0.95,
  "patterns_injected": 2,
  "injected_pattern_ids": ["auto-..."],
  "conversation_id": "..."
}
```

**Comando de verificación:**
```bash
tail -n 20 ~/.omnicursor/events.jsonl | \
  jq 'select(.event=="prompt_classified") | {matched_agent, score, patterns_injected, injected_pattern_ids}'
```

> **Nota:** Si `patterns_injected` es 0 en la primera sesión limpia, es normal — no hay patterns todavía. Después del Escenario 3 (pre-seed), vuelve a correr este prompt y verás inyección real.

---

## Scenario 2 — File Edit Auto-Lint

**Qué demostrar:** el hook `afterFileEdit` detecta el lenguaje del archivo editado, corre `ruff check` diagnósticamente, y loggea los findings sin modificar el archivo.

**Prompt para Cursor:**
```
Create eval/demo_autolint.py with an intentional unused import for hook-demo purposes. Do not fix the lint issue. Add one tiny function and finish with done.
```

**Evidencia esperada en Terminal 1:**
```json
{
  "event": "file_edited",
  "file_path": "eval/demo_autolint.py",
  "language": "python",
  "ruff_findings": 1,
  "conversation_id": "..."
}
```

`ruff_findings` counts non-empty `ruff` output lines, not unique rule IDs. In
practice any value `> 0` proves the hook ran and found a diagnostic.

**Comando de verificación:**
```bash
tail -n 50 ~/.omnicursor/events.jsonl | \
  jq 'select(.event=="file_edited") | {file_path, language, ruff_findings, conversation_id}'
```

> **Tip:** El archivo generado debería tener algo como `import os` sin usar. El hook nunca aplica `--fix` — solo reporta.

---

## Scenario 3 — Pattern Persistence / Injection

**Qué demostrar:** `learned_patterns.json` persiste entre sesiones. Un pattern aprendido/pre-seeded en la sesión A aparece en `injected_pattern_ids` de la sesión B.

### Por qué el live-learning es frágil

El aprendizaje de patterns requiere `session_outcome == "success"` AND `files_edited > 0`. Una sesión corta puede clasificarse como `abandoned`. Para eliminar esa aleatoriedad de la demo, se recomienda **pre-seedear** el pattern antes.

### Pre-seed (documentado — ejecutar antes de la demo)

```bash
python3 - <<'PY'
import json, time
from pathlib import Path

p = Path.home() / ".omnicursor" / "learned_patterns.json"
p.parent.mkdir(parents=True, exist_ok=True)

data = {"patterns": []}
if p.exists():
    try:
        data = json.loads(p.read_text())
    except Exception:
        data = {"patterns": []}

demo = {
    "pattern_id": "demo-pattern-omnicursor-preserve-marker",
    "domain": "debug_intelligence",
    "pattern": "debug demo marker pattern_sync learned_patterns",
    "keywords": ["demo_marker", "pattern_sync", "learned_patterns"],
    "description": "Demo pattern: preserve DEMO_MARKER comments when editing demo files.",
    "weight": 1.0,
    "created_at": time.time(),
    "last_seen": time.time(),
    "injection_count": 0,
    "utilization_successes": 0
}

patterns = data.setdefault("patterns", [])
patterns = [x for x in patterns if x.get("pattern_id") != demo["pattern_id"]]
patterns.append(demo)
data["patterns"] = patterns
p.write_text(json.dumps(data, indent=2) + "\n")
print(f"Pattern seeded: {p}")
PY
```

### Prompt Sesión B (después del pre-seed)

```
Debug this demo workflow: when editing files that contain DEMO_MARKER, preserve that marker and mention done when complete. Inspect or create docs/demo-pattern.md. Finish with done.
```

**Evidencia esperada en Terminal 1:**
```json
{
  "event": "prompt_classified",
  "matched_agent": "debug-intelligence",
  "patterns_injected": 1,
  "injected_pattern_ids": ["demo-pattern-omnicursor-preserve-marker"]
}
```

**Comando de verificación:**
```bash
tail -n 50 ~/.omnicursor/events.jsonl | \
  jq 'select(.event=="prompt_classified") | {matched_agent, patterns_injected, injected_pattern_ids}'
```

```bash
# Ver el pattern en el JSON local
jq '.patterns[] | select(.pattern_id=="demo-pattern-omnicursor-preserve-marker")' \
  ~/.omnicursor/learned_patterns.json
```

---

## Scenario 4 — Option B Durable Outbox

**Qué demostrar:** al terminar cada sesión (cualquier outcome), `stop.py` escribe un payload estructurado al outbox local. Este es el contrato que Option C drenará a Kafka/OmniIntelligence.

**Evidencia — al cerrar la sesión de Cursor:**

En Terminal 2 aparecerá automáticamente. Para ver el último registro:

```bash
tail -n 1 ~/.omnicursor/outbox.jsonl | jq .
```

**Campos esperados en el payload:**

```json
{
  "schema_version": "omnicursor.session_outcome.v1",
  "source": "omnicursor",
  "conversation_id": "...",
  "correlation_id": "...",
  "started_at": "2026-05-09T...",
  "ended_at": "2026-05-09T...Z",
  "session_status": "stopped",
  "session_outcome": "success",
  "session_outcome_reason": "...",
  "prompts_classified": 2,
  "files_edited": 1,
  "patterns_injected": 1,
  "injected_pattern_ids": ["demo-pattern-omnicursor-preserve-marker"],
  "matched_agent": "debugging",
  "matched_confidence": 0.85,
  "languages": ["python"],
  "shell_commands": {"allowed": 0, "denied": 0, "warned": 0}
}
```

**Narrativa para la cámara:**
> *"Este outbox es el contrato congelado. Cuando Option C llegue, solo cambia el sink: en lugar de escribir localmente, drena esto a Redpanda. Los campos están diseñados para ser consumidos directamente por omniintelligence sin traducción."*

---

## Scenario 5 — Hooks Disabled → MCP Fallback

**Estado actual:**
- Shell smoke: **pasa** (`run_local_review(dry_run=True)` → `ok: true`)
- Cursor UI smoke: **pendiente verificación manual**

**Pasos desde Cursor UI:**

1. Ir a Cursor Settings → Features → Hooks → deshabilitar temporalmente.
2. Confirmar que `.cursor/mcp.json` sigue activo (no tiene nada que ver con hooks).
3. Abrir un chat y usar la tool MCP `omnicursor-omnimarket` / `run_local_review`.
4. Esperar respuesta con `"ok": true`.
5. Re-habilitar hooks antes de continuar.

**Fallback si no se puede desde UI (demo de contingencia):**
```bash
OMNIMARKET_ROOT=/Users/jirustaroure/Desktop/OmniCursor/omnimarket \
  .venv/bin/python -c "
import json
from omnicursor.omnimarket_bridge import run_local_review
print(json.dumps(run_local_review(dry_run=True), indent=2, default=str))
"
```

**Narrativa para la cámara:**
> *"Incluso sin hooks, el sistema sigue funcionando. El bridge Omnimarket es independiente. Hooks y MCP son dos capas ortogonales — si una cae, la otra sigue en pie."*

---

## Docker / OmniIntelligence Note

**Docker NO se usa en la demo A+B.** La historia central es "local-first sin infraestructura".

Si se quiere mostrar **Option C readiness** como bonus opcional al final:

```bash
# Levantar solo el health de intelligence-reducer (no usar en demo principal)
docker compose up -d intelligence-reducer
curl http://127.0.0.1:18091/health
# Esperado: 200 OK (stub mode — solo /health, no /api/v1/patterns POST)
```

Luego apagarlo:
```bash
docker compose down
```

> **Honestidad importante:** el reducer corre en stub mode. Solo responde `/health`. No hay `POST` de session outcomes ni `/api/v1/patterns` funcionando. Eso es exactamente lo que B mínima documenta como "out of scope". Mostrarlo confirma que la arquitectura está lista sin exagerar el estado actual.

---

## Failure Playbook

| Síntoma | Causa probable | Remedio |
|---------|---------------|---------|
| `prompt_classified` no aparece | Hooks no habilitados en Cursor | Settings → Features → Hooks → verificar |
| `ruff_findings` es 0 | Import usado, sintaxis incorrecta, o `ruff` no disponible | Agregar `import os` sin usar y verificar `.venv/bin/ruff --version` |
| Pattern no se inyecta en Sesión B | Pattern no está en `learned_patterns.json` | Correr el pre-seed y verificar con `jq .patterns ~/.omnicursor/learned_patterns.json` |
| Outbox no crece | `stop.py` no corre o `conversation_id` vacío | Ver `~/.omnicursor/events.jsonl` para `session_stopped`; verificar hook activo |
| Outbox tiene líneas de test viejas | Tests corrieron antes | Usar `OMNICURSOR_OUTBOX_FILE=~/.omnicursor/demo-outbox.jsonl` |
| `run_local_review` falla desde shell | `OMNIMARKET_ROOT` no apunta a checkout válido | Verificar path y SHA con `ls $OMNIMARKET_ROOT/src/omnimarket/nodes/` |
| MCP falla desde Cursor UI | Server no inicializado o path incorrecto | Revisar `.cursor/mcp.json`, reiniciar Cursor |
| Docker falla | No requerido para A+B | Ignorar — no bloquea la demo |

---

## Demo Close

> *"Option A proves local intelligence — routing, learning, utilization tracking, and pattern injection, all without a network call. Option B proves durable bridge readiness — the outbox schema is frozen, the defensive sync is in place, and the MCP bridge is live. Option C is the next integration step: drain the outbox into Redpanda / omniintelligence and surface it in OmniDash."*
