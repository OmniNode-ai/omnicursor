# Handoff — Option A Closure

> **Location:** This file was moved from `docs/handoff.md` to keep the docs tree organized. The intelligence options write-up is [`docs/dev/INTELLIGENCE_LAYER_CURRENT_STATE_AND_OPTIONS.md`](../../../dev/INTELLIGENCE_LAYER_CURRENT_STATE_AND_OPTIONS.md).

**Fecha:** 2026-05-10  
**Rama:** julian/option-b-from-main  
**Commits recientes:**
- `bd9510a` chore(skills): sync hostile-reviewer to OmniClaude v4.0.0
- `01453a9` Merge PR: feat(intelligence): Option A — local pattern learning with utilization tracking and eviction
- `b8e8ae1` fix(lint): remove unused variable in test

---

## Objetivo de la sesión

Cerrar Option A del documento `# Intelligence Layer — Current State and Options.md` al 100%, implementando los 4 gaps que quedaron abiertos tras el merge de la rama `intelligence/option-a`. No empezar Option B.

---

## Estado inicial conocido

Option A está **parcialmente implementada**. Ya existen:

- `injection_count` y `utilization_successes` en cada record de `learned_patterns.json`
- Multiplier 1.5× aplicado a patterns con alta utilización
- Eviction por baja utilización (`_evict_low_utilization`, `_evict_overflow`)
- `write_session_patterns` llamado desde `stop.py` (solo en outcome `success`)

**Firma actual de `write_session_patterns`** (`src/omnicursor/pattern_writer.py:231`):
```python
def write_session_patterns(
    patterns_file: Path,
    events: List[Dict[str, Any]],
    files_edited: int,
) -> int:
```
No recibe `session_outcome` — la lógica de éxito/fallo vive en `stop.py`, no en el writer.

---

## Gaps de Option A (los 4 que cierran esta sesión)

### Gap 1 — `injected_pattern_ids` no registrado
- **Dónde:** `.cursor/hooks/scripts/user-prompt-submit.py` línea ~561/577
- **Estado actual:** `prompt_classified` loggea `patterns_injected: len(patterns)` (conteo entero)
- **Falta:** registrar `injected_pattern_ids: [p["pattern_id"] for p in patterns[:MAX_PATTERNS] if p.get("pattern_id")]`

### Gap 2 — `stop.py` solo llama al writer en `success`
- **Dónde:** `.cursor/hooks/scripts/stop.py` línea ~166
- **Estado actual:** `if summary["session_outcome"] == "success": write_session_patterns(...)`
- **Falta:** llamar al writer para cualquier outcome; el writer decide internamente qué hacer según `session_outcome`

### Gap 3 — `pattern_writer.py` usa `patterns_injected > 0` como booleano
- **Dónde:** `src/omnicursor/pattern_writer.py` línea ~225
- **Estado actual:** `"injected": int(evt.get("patterns_injected", 0)) > 0` — no identifica qué pattern fue inyectada
- **Falta:** consumir `injected_pattern_ids` desde eventos `prompt_classified` y actualizar métricas por ID real. Nueva semántica:
  - Cualquier outcome: `injection_count += 1` por cada ID inyectado existente
  - Solo `success`: `utilization_successes += 1` y aprendizaje de nuevos patrones

### Gap 4 — Escritura no atómica de `learned_patterns.json`
- **Dónde:** `src/omnicursor/pattern_writer.py` línea ~94 (`_save_patterns`)
- **Estado actual:** `path.write_text(...)` — write directo, riesgo de corrupción si el proceso muere a mitad
- **Falta:** temp file + `os.replace(tmp, path)`

---

## Plan de ejecución A → G

| Prompt | Modo | Objetivo |
|--------|------|----------|
| A | Plan Mode | Plan completo: IDs, firma, atomic write, tests |
| B | Ejecutar | Implementar `injected_pattern_ids` en `user-prompt-submit.py` |
| C | Plan Mode | Diseño de cambios en `pattern_writer.py` |
| D | Ejecutar | Implementar nueva firma y semántica en `pattern_writer.py` |
| E | Plan Mode | Diseño de cableado en `stop.py` |
| F | Ejecutar | Implementar `stop.py` para cualquier outcome |
| G | Verificar | `ruff check` + `pytest -q` completo, declarar Option A cerrada |
| H | Opcional | Actualizar el doc `# Intelligence Layer — Current State and Options.md` |

Los prompts exactos están en `docs/archive/dev/OptionA-Prompts.md`.

---

## Archivos que se tocarán

| Archivo | Cambio esperado |
|---------|----------------|
| `.cursor/hooks/scripts/user-prompt-submit.py` | Agregar `injected_pattern_ids` al log y al payload de `send_event` |
| `src/omnicursor/pattern_writer.py` | Nueva firma con `session_outcome`, lógica por ID, helper de `pattern_id` determinístico, backfill legacy, escritura atómica |
| `.cursor/hooks/scripts/stop.py` | Llamar `write_session_patterns` para cualquier outcome, cargar events una sola vez |
| `tests/test_suite_event1_prompt.py` | Cubrir `injected_pattern_ids` en log y payload |
| `tests/test_pattern_writer.py` | ~14 tests nuevos (ver lista completa en Prompt D) |
| `tests/test_suite_event4_stop.py` | ~6 tests cubriendo todos los outcomes |

**No tocar:**
- `.cursor/mcp.json`
- `.cursor/rules/03-omnicursor-ownership.mdc`
- `explanation.md`
- Docs existentes (salvo Prompt H opcional)

---

## Tests esperados

### `test_suite_event1_prompt.py`
- patterns con `pattern_id` → aparecen en `injected_pattern_ids`
- pattern sin `pattern_id` o string vacío → omitido
- lista respeta `MAX_PATTERNS`
- `patterns_injected` sigue siendo int con valor correcto
- `send_event` recibe `injected_pattern_ids`

### `test_pattern_writer.py` (nuevos)
- `test_new_pattern_gets_deterministic_id`
- `test_same_domain_and_pattern_key_get_same_id`
- `test_legacy_record_without_id_gets_backfilled`
- `test_existing_seed_pattern_id_is_preserved`
- `test_failed_outcome_increments_injection_count_only`
- `test_abandoned_outcome_increments_injection_count_only`
- `test_unknown_outcome_increments_injection_count_only`
- `test_success_outcome_with_injected_id_increments_injection_and_utilization`
- `test_failed_outcome_does_not_create_new_patterns_from_snippet`
- `test_success_with_zero_files_edited_updates_metrics_but_does_not_learn`
- `test_unknown_injected_id_is_skipped_silently`
- `test_missing_injected_pattern_ids_field_does_not_crash`
- `test_atomic_write_uses_replace`
- `test_low_utilization_pattern_is_evicted_after_failed_injections`

### `test_suite_event4_stop.py` (nuevos/adaptados)
- `test_success_session_calls_writer_with_success`
- `test_failed_session_calls_writer_for_metrics`
- `test_abandoned_session_calls_writer_for_metrics`
- `test_unknown_session_calls_writer_for_metrics`
- `test_session_without_conversation_id_does_not_call_writer`
- `test_session_without_injected_ids_does_not_crash`

---

## Decisiones abiertas

1. **`pattern_id` determinístico para patterns nuevas autoaprendidas:** `auto-` + `sha1(f"{domain}:{pattern_key}".encode()).hexdigest()[:12]`. Confirmar que `pattern_key` es el fingerprint normalizado ya persistido en el campo `"pattern"`.
2. **Deduplicación dentro de un evento:** sí, deduplicar IDs dentro del mismo `prompt_classified`. No deduplicar a nivel sesión (una pattern inyectada en 2 prompts distintos cuenta como 2 injections).
3. **IDs desconocidos en `injected_pattern_ids`:** skip silencioso — no crear patterns fantasmas.
4. **Backfill de records legacy sin `pattern_id`:** aplicar el mismo helper usando `domain + pattern`. No sobrescribir IDs de seed patterns.
5. **Compatibilidad de `events.jsonl` viejos** sin `injected_pattern_ids`: si el campo falta o está vacío, no tocar métricas por ID y seguir el flujo normal.

---

## Señales de alarma

- Si aparece HTTP, Kafka, Redpanda o intelligence-reducer → detener, es Option B/C.
- Si el writer crea patterns nuevas para IDs desconocidos → detener, crea fantasmas.
- Si `ruff` falla en Prompt G → corregir antes de declarar Option A completa.
- Si `pytest -q` no pasa completo → no declarar Option A cerrada.

---

## Log de progreso

| Prompt | Estado | Notas |
|--------|--------|-------|
| A — Plan inicial | Hecho | Plan aprobado en Plan Mode |
| B — user-prompt-submit.py | Hecho | +5 tests (TestInjectedPatternIds), 142 passed |
| C — Plan pattern_writer | Hecho | Cubierto en Plan Mode |
| D — Implementar pattern_writer | Hecho | +17 tests, 41 passed; _make_pattern_id, backfill, escritura atómica, nueva firma |
| E — Plan stop.py | Hecho | Cubierto en Plan Mode |
| F — Implementar stop.py | Hecho | +6 tests (TestWriterInvocation), 98 passed; writer llamado en cualquier outcome |
| G — Verificación final | Hecho | ruff OK, 572 passed (1.21s) |
| H — Cierre documental | Hecho | Option A marcada como complete en `# Intelligence Layer — Current State and Options.md`; caveat de proxy preservado; Option B/C intactas |

---

## Estado final

Option A declarada completa — verificado 2026-05-10:
- [x] `ruff check src/ tests/ .cursor/hooks/` pasa limpio
- [x] `pytest -q` pasa completo — 572 passed, 1.21s
- [x] `injected_pattern_ids` aparece en eventos `prompt_classified`
- [x] `stop.py` llama al writer para cualquier outcome
- [x] `pattern_writer.py` incrementa `injection_count` en non-success
- [x] `pattern_writer.py` incrementa `utilization_successes` solo en success
- [x] `_save_patterns` usa temp file + `os.replace`
- [x] Doc `# Intelligence Layer — Current State and Options.md` actualizado: Option A marcada como complete; caveat de proxy explícito; Option B/C sin tocar; Current Wiring Gaps preservados

---

## Cierre de sesión

Option A está cerrada — implementación verificada y documentación alineada. Nada más por hacer en este track.

### Comandos de verificación corridos (revalidados al cierre documental)

```bash
.venv/bin/python -m ruff check src/ tests/ .cursor/hooks/
# → All checks passed!

.venv/bin/python -m pytest -q
# → 572 passed in 1.05s
```

### Archivos tocados en Prompt H

- `# Intelligence Layer — Current State and Options.md`: marca Option A como complete (con fecha y referencia a la rama), reemplaza el bloque "**Gap:** weight updates ..." por "**Status:** Gap closed + **Caveat:** proxy, no LLM check", reescribe "What changes" como "What changed (delivered)" enumerando los entregables concretos, y tacha el bullet 1 de Recommended Path como hecho.
- `docs/handoff.md`: este archivo — Prompt H marcado Hecho, checklist final + sección de cierre.

### Próximos pasos — Option B (no empezada)

Cuando se retome, hacer en este orden:

1. **Fix de puerto en `pattern_sync.py`**: cambiar el default `http://127.0.0.1:8053` → `http://127.0.0.1:18091` para alinearse con `intelligence-reducer` del compose stack.
2. **Verificar la API de `intelligence-reducer`** que efectivamente expone: documentar la shape real (endpoint, payload, response) antes de escribir cliente. Es la mayor incógnita.
3. **Write path** desde `stop.py`: POST `session_outcome + injected_pattern_ids` al reducer tras cada `success`, con fallback silencioso al JSON local si el stack está offline.
4. **Namespace**: decidir entre alinear a `onex.evt.omniclaude.*` o registrar consumidor nuevo para `onex.evt.omnicursor.*` en omniintelligence. Es cambio upstream — confirmar antes de tocar.
5. **`pattern_sync.py` read path**: ya existe y se controla con `OMNICURSOR_PATTERN_SYNC_HTTP=1`; tras el fix de puerto debería traer patterns del reducer al JSON local.
6. **Tests**: cliente HTTP con mock del reducer, tests de fallback cuando el endpoint no responde, tests de namespace.

### Guardrails Option B (mismo que Option A pero invertidos)

- Hooks **siguen siendo stdlib only** — `urllib.request` está OK, librerías externas no.
- JSON local sigue siendo el read cache canónico — la HTTP path es enriquecimiento, no reemplazo.
- No tocar Kafka / Redpanda — eso es Option C, año-2.
- Fallback obligatorio: stack offline → degradación a comportamiento Option A puro, sin crashear el hook.

### Rama y commits

- Rama actual: `julian/omnicursor-optionB` (el handoff fue iniciado en `julian/option-b-from-main`; rebautizada/movida)
- Último commit antes del cierre documental: `6113441 fix: convert omnimarket into normal directory`
- Los cambios de Prompt H quedan untracked hasta que decidas commitear

---

# Handoff — Option B Mínima

**Fecha de creación:** 2026-05-09
**Rama:** `julian/omnicursor-optionB`
**Continuación de:** Option A Closure (sección anterior)

---

## Objetivo de sesión

Implementar **Option A → Option B mínima** como combinación local sólida. B mínima no intenta integrar OmniCursor con OmniIntelligence vía HTTP real — el `intelligence-reducer` upstream corre en stub mode y no expone los endpoints que el doc original prometía. En su lugar, B mínima entrega el contrato congelado y los fallbacks defensivos que dejan la base limpia para que **Option C** (integración Kafka/OmniIntelligence/OmniDash real) pueda construirse encima sin tirar nada.

## Estado inicial conocido

- **Option A**: completa. Verificado 2026-05-10 con 572 tests verdes y `ruff` limpio. Toda la infraestructura local (`injection_count`, `utilization_successes`, multiplier 1.5×, eviction, escritura atómica) funcionando.
- **Doc `# Intelligence Layer — Current State and Options.md`**: actualizado en Prompt H para reflejar A complete, B next, C future/long-term. Caveat de proxy preservado.
- **`docs/handoff.md`** (este archivo): contiene cierre de Option A arriba. Esta sección agrega la fase B.
- **Reducer upstream**: corre en stub mode, solo `/health` responde. `GET /api/v1/patterns` retorna 404. No hay `POST` para session outcome. Codex verificó contra `omniintelligence` main.
- **Bridge canónico per CLAUDE.md** (líneas 117-130): Omnimarket por subprocess (`python -m omnimarket.nodes.<node>`), NO llamadas HTTP directas a intelligence-reducer.
- **omnimarket/**: estado post-commit `6113441 fix: convert omnimarket into normal directory` pendiente de auditar en Prompt A. Codex previamente verificó que `run_local_review` funciona con `omnimarket-main.zip` extraído.
- **Test files que los prompts asumen**: `test_pattern_sync.py`, `test_omnimarket_bridge.py`, `test_mcp_omnimarket_bridge.py` — existencia a verificar en Prompt A. Si no existen, el alcance de B incluye crear suites nuevas, no solo extender.
- **Rama divergente**: handoff anterior cierra en `julian/option-b-from-main`; rama actual es `julian/omnicursor-optionB`. Decisión consciente vs accidente — verificar.

## Alcance de B mínima

1. **Outbox durable de session outcomes** — `~/.omnicursor/outbox.jsonl`. Cada `stop.py` apendiza una línea JSON con el payload completo de la sesión, para cualquier outcome (success/failed/abandoned/unknown). Es la pieza central: cuando C aterrice, este outbox se drena a Kafka u Omnimarket sin perder histórico.
2. **`pattern_sync` defensivo** — probe `/health` antes de fetch, manejo silencioso de stub mode y offline, escritura atómica del JSON local, default port `8053 → 18091`, respeta `OMNIINTELLIGENCE_URL`.
3. **MCP/Omnimarket fallback funcional** — escenario demo 4 (hooks off → MCP-only). `.cursor/mcp.json` apuntando a checkout válido; `run_local_review` retorna `ok: true`. Sin clonar en runtime ni commitear checkouts.
4. **Docs alineadas** — `# Intelligence Layer ...md` con sección "B mínima local-first" honesta; `.env.omninode.example` documentando env vars nuevas; este `handoff.md` con log final.

## Fuera de alcance (queda para Option C)

- ❌ Kafka producer / Redpanda
- ❌ POST real a `intelligence-reducer` (no hay endpoint)
- ❌ Namespace alignment (`onex.evt.omnicursor.*` ↔ `onex.evt.omniclaude.*`)
- ❌ Traducción de `pattern_id` `auto-<sha1>` → UUID upstream
- ❌ OmniDash integration
- ❌ Rotación/drenaje del outbox (C asume el drain)
- ❌ Emit socket fix (`emit_client.py` sigue como Current Wiring Gap)

## Plan de ejecución 0 → H

| Prompt | Modo | Objetivo |
|---|---|---|
| 0 | Execute | Setup: este handoff (no toca código de comportamiento) |
| A | Plan Mode | Audit codebase + test files + estado real omnimarket + fallback de bloqueo MCP. Sin escritura. |
| B | Execute | Implementar outbox local durable + tests. Actualizar handoff. |
| C | Plan Mode | Diseño de `pattern_sync` defensivo (probe, atomic write, port fix). Sin escritura. |
| D | Execute | Implementar `pattern_sync` + tests. Actualizar handoff. |
| E | Plan Mode | Auditar MCP/Omnimarket post-commit `6113441`. Definir checkout strategy + decisión de fallback si bloqueo MCP no es resoluble. Sin escritura. |
| F | Execute | Implementar fix MCP, smoke `run_local_review`. Actualizar handoff. |
| G | Execute | Docs alineadas (`# Intelligence Layer ...md`, `.env.omninode.example`). |
| H | Execute | Verificación final: ruff + pytest completo + smoke manual escenario 4. Marcar B mínima como cerrada. |

**Restricciones operacionales:**
- Diffs pequeños, un entregable por prompt.
- Pytest scoped tras cada Execute. Suite completa solo en Prompt H.
- `docs/handoff.md` actualizado en cada Execute prompt (no en Plan Mode).
- Nunca tocar: `.cursor/mcp.json` sin Plan E aprobado, `.cursor/rules/03-omnicursor-ownership.mdc`, `explanation.md`.

## Archivos probables a tocar

| Archivo | Cambio |
|---|---|
| `src/omnicursor/session_outbox.py` | Nuevo módulo (stdlib only): writer del outbox JSONL |
| `.cursor/hooks/scripts/stop.py` | Llamar al outbox writer tras `write_session_patterns` |
| `src/omnicursor/sync/pattern_sync.py` | Probe `/health`, port fix `18091`, atomic write |
| `.cursor/hooks/lib/pattern_sync.py` | Espejar cambios si aplica (verificar duplicación per `OMNICLAUDE_TO_CURSOR_PORT.md`) |
| `.cursor/mcp.json` | Apuntar a checkout válido de omnimarket |
| `src/omnicursor/omnimarket_bridge.py` | Solo si requiere ajuste menor — sin rediseño |
| `tests/test_suite_event4_stop.py` | Tests de integración outbox + stop.py |
| `tests/test_pattern_sync.py` | Crear si no existe; tests de probe defensivo |
| `tests/test_omnimarket_bridge.py` | Crear si no existe; smoke + assertions |
| `tests/test_mcp_omnimarket_bridge.py` | Crear si no existe; validación de config |
| `# Intelligence Layer — Current State and Options.md` | Sección B mínima honesta |
| `.env.omninode.example` | Documentar `OMNICURSOR_OUTBOX_FILE`, `OMNICURSOR_PATTERN_SYNC_HTTP`, `OMNIINTELLIGENCE_URL`, `OMNIMARKET_ROOT` |
| `docs/handoff.md` | Log de progreso vivo (este archivo) |
| `.gitignore` | Confirmar que `omnimarket-main/` y `omnimarket-main.zip` están ignorados si se usan localmente |

## Tests esperados

### `tests/test_suite_event4_stop.py` (extender)
- `stop.py` escribe 1 línea válida en outbox por sesión, para los 4 outcomes.
- Múltiples eventos `prompt_classified` en una sesión → `injected_pattern_ids` deduplicados preservando orden.
- Fallo del outbox (disco lleno, permission denied) no rompe `stop.py` — retorna `{}` normal.
- Option A sigue escribiendo `learned_patterns.json` como antes.
- `ended_at` en formato ISO 8601 UTC con sufijo `Z`.
- Override por `OMNICURSOR_OUTBOX_FILE` funciona en tests.

### `tests/test_pattern_sync.py` (crear o extender)
- Offline (connection refused / timeout) → return False, no toca JSON local.
- `/health` responde stub mode → return False, no toca JSON local.
- `/health` OK + `/api/v1/patterns` 404 → return False, no toca JSON local.
- `/api/v1/patterns` retorna lista válida o `{"patterns": [...]}` → escribe normalizado.
- Response inválido (JSON corrupto, schema incorrecto) → no pisa JSON local.
- Default URL usa puerto `18091`.
- `OMNIINTELLIGENCE_URL` override tiene prioridad.
- Escritura atómica vía `tempfile.mkstemp` + `os.replace`.

### `tests/test_omnimarket_bridge.py` + `tests/test_mcp_omnimarket_bridge.py` (crear si no existen)
- Smoke: `run_local_review(dry_run=True)` retorna `ok: true` con checkout real.
- `OMNIMARKET_ROOT` desapuntado → fallback a `omnimarket-main/` en repo root.
- `.cursor/mcp.json` config válida.
- `PYTHONPATH` injection correcto en subprocess.

## Riesgos

1. **MCP/Omnimarket es el más frágil**. Depende de estado de checkout, paths absolutos, sandbox Cursor. Si Prompt E surfacea bloqueo no resoluble (configuración externa a Cursor o checkout no reproducible), decisión documentada: B mínima entrega 1+2+4 y MCP queda como bloqueo conocido. Demo entonces cubre solo escenarios 1, 2, 3 (no el 4).
2. **Test files inexistentes**. Si `test_pattern_sync.py`, `test_omnimarket_bridge.py`, `test_mcp_omnimarket_bridge.py` no existen, el alcance real de B sube a creación de suites nuevos. Verificar primero en Prompt A para ajustar estimación.
3. **Concurrent writes al outbox**. Append en POSIX es atómico solo hasta `PIPE_BUF` (~4KB). Payloads pequeños son seguros. Si crecen, considerar `fcntl.flock` — pero es Option C scope. Documentar decisión consciente en Prompt B.
4. **Coexistencia `omnimarket/` vs `omnimarket-main/`**. Per CLAUDE.md, fallback es `omnimarket-main/` en repo root. Si ambos coexisten post-commit `6113441`, decidir cuál gana sin romper la otra ruta. Tarea de Plan E.
5. **Rama divergente**. Handoff de Option A dice rama `julian/option-b-from-main`; rama actual es `julian/omnicursor-optionB`. Verificar si es rebranding consciente o conviene normalizar antes de empezar Prompt A.
6. **Doc viejo del Intelligence Layer** describía Option B como "POST directo a intelligence-reducer". Prompt G debe reescribir esa sección para que diga "B mínima local-first" sin promesas falsas.

## Log de progreso

| Prompt | Estado | Notas |
|---|---|---|
| 0 — Setup handoff B mínima | Hecho | Este archivo actualizado con sección "Handoff — Option B Mínima" |
| A — Plan general (auditoría) | Hecho | Plan Mode con 3 Explore agents + 1 Plan agent. Audit completo confirmó: test files existen, `omnimarket/` resuelto con clone fresco (SHA `ce0f3bec8a049bb9ae728adee2d053fd4cebe28b` branch `main`), dos copias de pattern_sync, bugs latentes en ambas, `session_outbox.py` a crear. `.gitignore` actualizado con `omnimarket/`. Plan aprobado. |
| 1 — Bridge housekeeping | Hecho | `.gitignore` +`omnimarket/`. Smoke: `OMNIMARKET_ROOT=.../omnimarket run_local_review(dry_run=True)` → `ok: true`. Nota: fuera del contexto MCP hay que pasar `OMNIMARKET_ROOT` explícito; Cursor lo inyecta desde `.cursor/mcp.json`. |
| 2 — Pattern_sync defensivo | Hecho | `src/omnicursor/sync/pattern_sync.py` reescrito con probe `/health`, port `18091`, atomic write, guard no-overwrite. `lib/pattern_sync.py` → shim. +7 tests (`TestPatternSyncDefensive`). 67 passed, ruff OK. |
| 3 — Crear session_outbox.py | Hecho | `src/omnicursor/session_outbox.py` (stdlib only, append POSIX atómico). `tests/test_session_outbox.py` (11 tests). ruff OK. |
| 4 — Integrar outbox en stop.py | Hecho | `_build_outbox_payload` helper + `write_session_outcome` call en main(). +8 tests (`TestSessionOutbox`). 106 passed (stop+pattern_writer), ruff OK. |
| 5 — Docs + env vars | Hecho | `.env.omninode.example` +4 vars (OMNIMARKET_ROOT, OMNIINTELLIGENCE_URL, OMNICURSOR_PATTERN_SYNC_HTTP, OMNICURSOR_OUTBOX_FILE). `# Intelligence Layer ...md`: Option B reescrita como "B mínima local-first", Recommended Path actualizado (A+B done, C next). |
| 6 — Verificación final | Hecho | ruff OK, 598 passed (572 originales + 26 nuevos). Option B mínima cerrada. |

### Checkout Omnimarket canónico
- **Path:** `/path/to/omnimarket`
- **SHA:** `ce0f3bec8a049bb9ae728adee2d053fd4cebe28b`
- **Branch:** `main`
- **Estado:** clone fresco real, `src/omnimarket/nodes/node_local_review/__main__.py` existe
- **Ignorado por:** `.gitignore` (línea `omnimarket/` agregada en Prompt 1)
- **`.cursor/mcp.json`:** apunta a este path vía `OMNIMARKET_ROOT` — no se toca

## Criterios de cierre — Option B mínima

Option B declarada completa — verificado 2026-05-09:
- [x] Option A intacta — `pytest -q` 598 passed (572 + 26 nuevos), ruff limpio
- [x] `~/.omnicursor/outbox.jsonl` recibe payload `omnicursor.session_outcome.v1` en cada sesión, todos los outcomes
- [x] `OMNICURSOR_PATTERN_SYNC_HTTP=1` no rompe contra stack offline ni stub (probe defensivo)
- [x] `pattern_sync` nunca pisa JSON local ante error/stub/response inesperado
- [x] `run_local_review(dry_run=True)` retorna `ok: true` con `OMNIMARKET_ROOT=.../omnimarket` (SHA `ce0f3bec...`)
- [x] `# Intelligence Layer ...md` describe B mínima honestamente; C como próximo paso
- [x] `.env.omninode.example` lista 4 env vars de B (OMNIMARKET_ROOT, OMNIINTELLIGENCE_URL, OMNICURSOR_PATTERN_SYNC_HTTP, OMNICURSOR_OUTBOX_FILE)
- [x] `.gitignore` excluye `omnimarket/`
- [ ] Smoke manual escenario 4 (hooks off → MCP-only) — pendiente verificación manual en Cursor

## Próximos pasos — Option C

1. **Kafka producer**: drainer para `~/.omnicursor/outbox.jsonl` → `omnibase_infra` Redpanda. Requiere sidecar (hooks deben seguir siendo stdlib-only).
2. **Namespace alignment**: decidir `onex.evt.omniclaude.*` vs registrar consumidor nuevo `onex.evt.omnicursor.*` en `omniintelligence`. Coordinación upstream.
3. **Traducción de IDs**: `auto-<sha1>` → UUID de `pattern_injections` en PostgreSQL.
4. **OmniDash**: alinear namespace de sesiones OmniCursor con el dashboard.
5. **quality-scoring-compute**: LLM-based utilization scoring para cerrar el loop real (vs el proxy de Option A/B).
