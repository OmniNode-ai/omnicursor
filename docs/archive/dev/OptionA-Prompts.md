# Option A — Prompts Listos Para Copiar y Pegar

Fecha: 2026-05-10

Objetivo: cerrar Option A del documento `INTELLIGENCE_LAYER_CURRENT_STATE_AND_OPTIONS.md` al 100%, sin empezar Option B.

Veredicto actual: Option A esta parcialmente implementada. Ya existen `injection_count`, `utilization_successes`, multiplier `1.5x` y eviction por baja utilizacion, pero falta cerrar la semantica real:

- `prompt_classified` registra cuantas patterns se inyectaron, no cuales.
- `stop.py` solo llama al writer en `success`; outcomes fallidos no incrementan `injection_count`.
- `pattern_writer.py` usa `patterns_injected > 0` como booleano y le da credito a una pattern derivada del prompt actual, no a la pattern realmente inyectada.
- `_save_patterns` usa escritura directa, aunque el doc menciona atomic rename.

Usa estos prompts uno por uno. No pegues todos juntos.

Orden recomendado:

1. Prompt A en Plan Mode
2. Prompt B ejecutar
3. Prompt C en Plan Mode
4. Prompt D ejecutar
5. Prompt E en Plan Mode
6. Prompt F ejecutar
7. Prompt G verificar
8. Prompt H opcional para documentar cierre

---

## Prompt A — Plan Mode Inicial

```text
[Usa Plan Mode]

Restore de contexto:
Estamos en /Users/jirustaroure/Desktop/OmniCursor.

Objetivo global:
Cerrar Option A del documento "INTELLIGENCE_LAYER_CURRENT_STATE_AND_OPTIONS.md" al 100%, sin implementar Option B.

Definicion correcta de Option A:
- Todo sigue local y stdlib-only.
- user-prompt-submit.py debe registrar que patrones fueron inyectados por ID, no solo cuantos.
- stop.py debe actualizar metricas de patrones inyectados en cualquier outcome: success, failed, abandoned, unknown.
- pattern_writer.py debe incrementar injection_count para cada pattern_id inyectado en cualquier sesion.
- pattern_writer.py debe incrementar utilization_successes solo si session_outcome == "success".
- pattern_writer.py debe aprender patrones nuevos desde prompt_snippet solo en success + files_edited > 0.
- learned_patterns.json sigue siendo el read cache local.
- No HTTP POST, no Kafka, no Redpanda, no intelligence-reducer, no Option B.

Estado actual conocido:
- Ya existen injection_count y utilization_successes.
- Ya existe multiplier 1.5x.
- Ya existe eviction por baja utilizacion.
- Gap #1: prompt_classified solo loggea patterns_injected: len(patterns), no injected_pattern_ids.
- Gap #2: stop.py solo llama pattern_writer en success; failures no incrementan injection_count.
- Gap #3: _save_patterns usa write_text directo, no atomic rename.

Exclusiones:
- No tocar .cursor/mcp.json.
- No tocar explanation.md.
- No tocar .cursor/rules/03-omnicursor-ownership.mdc.
- No editar docs viejos.

Lee estos archivos en orden:
- "INTELLIGENCE_LAYER_CURRENT_STATE_AND_OPTIONS.md"
- .cursor/hooks/scripts/user-prompt-submit.py
- .cursor/hooks/scripts/stop.py
- src/omnicursor/pattern_writer.py
- tests/test_pattern_writer.py
- tests/test_suite_event1_prompt.py
- tests/test_suite_event4_stop.py

No edites codigo todavia.

Entrega un plan de implementacion dividido en pasos pequenos. Incluye:
1. Firma final propuesta para write_session_patterns, incluyendo session_outcome.
2. Estrategia de pattern_id deterministico:
   - Formula exacta.
   - Como se backfillea en records legacy sin pattern_id.
   - Como se preservan IDs existentes, incluyendo seed patterns.
3. Cambios exactos en user-prompt-submit.py:
   - Campo nuevo a loggear.
   - Campo existente que se mantiene por compatibilidad.
4. Cambios exactos en stop.py:
   - Como llama al writer para success, failed, abandoned y unknown.
5. Tests nuevos o modificados, un bullet por test.
6. Riesgos de compatibilidad:
   - learned_patterns.json viejo sin pattern_id.
   - events.jsonl viejo sin injected_pattern_ids.
7. Plan de escritura atomica con temp file + os.replace.

No implementes. Solo plan. Pide confirmacion al final.
```

---

## Prompt B — Implementar IDs En El Prompt Hook

```text
Restore de contexto:
Estamos en /Users/jirustaroure/Desktop/OmniCursor.

Objetivo:
Cerrar la primera parte de Option A local, sin Option B.

Definicion relevante:
- user-prompt-submit.py debe registrar que patrones fueron inyectados por ID, no solo cuantos.
- Mantener todo stdlib-only.
- No HTTP, no Kafka, no Redpanda, no intelligence-reducer.

Estado actual:
- En .cursor/hooks/scripts/user-prompt-submit.py, despues de filtrar patterns, el evento prompt_classified registra patterns_injected: len(patterns).
- Falta injected_pattern_ids.

Exclusiones:
- No tocar .cursor/mcp.json.
- No tocar explanation.md.
- No tocar .cursor/rules/03-omnicursor-ownership.mdc.
- No editar docs viejos.

Implementa solo esta parte:
1. En .cursor/hooks/scripts/user-prompt-submit.py, despues de calcular `patterns`, crea:

   injected_pattern_ids = [
       p.get("pattern_id", "")
       for p in patterns[:MAX_PATTERNS]
       if p.get("pattern_id")
   ]

2. Mantén `patterns_injected: len(patterns)` por compatibilidad.
3. Agrega `injected_pattern_ids` al log_event de `prompt_classified`.
4. Agrega `injected_pattern_ids` al payload de send_event("onex.cmd.omnicursor.cursor-hook-event.v1", ...).
5. No cambies el systemMessage salvo necesidad estricta.
6. No implementes Option B.

Tests:
Actualiza tests/test_suite_event1_prompt.py para cubrir:
- Si los patterns filtrados tienen pattern_id, aparecen en injected_pattern_ids del log.
- Un pattern sin pattern_id o con string vacio se omite de injected_pattern_ids.
- La lista respeta MAX_PATTERNS.
- patterns_injected sigue siendo int y conserva el valor esperado.
- send_event recibe injected_pattern_ids cuando send_event esta monkeypatcheado.

Corre:
.venv/bin/python -m pytest -q tests/test_suite_event1_prompt.py

Reporta:
- Archivos modificados.
- Resumen del diff.
- Output exacto de pytest.
```

---

## Prompt C — Plan Mode Para Pattern Writer

```text
[Usa Plan Mode]

Restore de contexto:
Estamos en /Users/jirustaroure/Desktop/OmniCursor.

Objetivo:
Disenar el cierre semantico de Option A en src/omnicursor/pattern_writer.py, sin implementar Option B.

Definicion correcta de Option A:
- Usar injected_pattern_ids desde eventos prompt_classified.
- Incrementar injection_count para cada pattern_id inyectado en cualquier outcome.
- Incrementar utilization_successes solo si session_outcome == "success".
- Aprender patrones nuevos desde prompt_snippet solo si session_outcome == "success" y files_edited > 0.
- learned_patterns.json sigue siendo el read cache local.
- Todo stdlib-only.

Estado actual:
- pattern_writer.py ya tiene injection_count, utilization_successes, multiplier y eviction.
- Pero usa patterns_injected > 0 como booleano.
- Eso no identifica que pattern fue inyectada.
- stop.py solo llama al writer en success.

Exclusiones:
- No tocar .cursor/mcp.json.
- No tocar explanation.md.
- No tocar .cursor/rules/03-omnicursor-ownership.mdc.
- No editar docs viejos.

Disena el cambio en src/omnicursor/pattern_writer.py sin editar todavia.

Firma propuesta:
write_session_patterns(
    patterns_file: Path,
    events: List[Dict[str, Any]],
    files_edited: int,
    session_outcome: str,
) -> int

Semantica requerida:
- Para cada event prompt_classified, leer injected_pattern_ids si existe.
- Deduplicar IDs dentro del mismo evento para evitar duplicados accidentales.
- No deduplicar a nivel sesion: si la misma pattern fue inyectada en dos prompts distintos, cuenta como dos injections.
- Si session_outcome == "success":
  - Para cada ID inyectado existente en learned_patterns.json: injection_count += 1, utilization_successes += 1, weight += WEIGHT_INCREMENT * UTILIZATION_SUCCESS_WEIGHT_MULTIPLIER.
  - Si files_edited > 0: aprender/upsertear nuevos patrones desde prompt_snippet, como hoy.
  - Si files_edited == 0: no aprender nuevos patrones, pero si actualizar metricas por ID.
- Si session_outcome != "success":
  - Para cada ID inyectado existente: injection_count += 1.
  - No incrementar utilization_successes.
  - No incrementar weight.
  - No aprender nuevos patrones desde prompt_snippet.

pattern_id deterministico:
- Para patrones nuevos autoaprendidos, usar un ID deterministico prefijado, por ejemplo:
  auto- + sha1(f"{domain}:{pattern_key}".encode("utf-8")).hexdigest()[:12]
- pattern_key debe ser el fingerprint normalizado que ya se persiste en el campo "pattern".
- Para records legacy sin pattern_id, backfillear con el mismo helper usando domain + pattern.
- Preservar cualquier pattern_id existente. No sobrescribir IDs de seed patterns ni IDs que vengan de sync.

Escritura atomica:
- Escribir JSON a un archivo temporal en el mismo directorio.
- Reemplazar el archivo final con os.replace(tmp, path).
- Limpiar tmp si ocurre error, si es razonable.

Edge cases:
- Si injected_pattern_ids falta o esta vacio: no tocar metricas por ID; seguir con el resto del flujo.
- Si un injected pattern_id no existe en learned_patterns.json: skip silencioso; no crear pattern fantasma.
- Si learned_patterns.json no existe: no crashear.
- Si el JSON viejo no trae injection_count/utilization_successes: normalizar a 0 como ya hace hoy.

Eviction:
- Mantener _evict_low_utilization y _evict_overflow.
- Ejecutarlas despues de updates de metricas y aprendizaje.

Entrega:
1. API exacta y helpers internos que vas a agregar.
2. Lista de tests nuevos con nombre y asercion central.
3. Plan de migracion para learned_patterns.json legacy.
4. Compatibilidad esperada con tests existentes.

No implementes. Solo plan. Pide confirmacion al final.
```

---

## Prompt D — Implementar Pattern Writer

```text
Restore de contexto:
Estamos en /Users/jirustaroure/Desktop/OmniCursor.

Objetivo:
Implementar el cierre semantico de Option A en src/omnicursor/pattern_writer.py, sin Option B.

Definicion correcta:
- injection_count sube para cada pattern_id inyectado en cualquier outcome.
- utilization_successes sube solo si session_outcome == "success".
- El aprendizaje de nuevos patrones desde prompt_snippet ocurre solo en success + files_edited > 0.
- Si una pattern fue inyectada pero la sesion falla, esa pattern debe acumular injection_count sin success, para que pueda ser evicted por baja utilizacion.

Estado actual:
- pattern_writer.py usa patterns_injected > 0 como booleano.
- Falta actualizar patterns existentes por ID.
- Falta escritura atomica.

Exclusiones:
- No tocar .cursor/mcp.json.
- No tocar explanation.md.
- No tocar .cursor/rules/03-omnicursor-ownership.mdc.
- No editar docs viejos.
- No implementar HTTP/Kafka/Option B.

Implementa en src/omnicursor/pattern_writer.py:
- Helper deterministico para pattern_id autoaprendido:
  auto- + sha1(f"{domain}:{pattern_key}".encode("utf-8")).hexdigest()[:12]
- Backfill de pattern_id en _load_patterns para records legacy sin ID.
- Preservar IDs existentes.
- Escritura atomica con temp file + os.replace.
- Nueva firma:
  write_session_patterns(patterns_file, events, files_edited, session_outcome) -> int
- Retorno: numero de records cambiados o escritos, contando metric updates y nuevos/upserted learned patterns.
- Nueva logica basada en injected_pattern_ids.
- Deduplicar IDs dentro de un mismo evento.
- No crear patterns fantasmas para injected IDs desconocidos.
- Mantener eviction al final.

Actualiza tests/test_pattern_writer.py:
- test_new_pattern_gets_deterministic_id
- test_same_domain_and_pattern_key_get_same_id
- test_legacy_record_without_id_gets_backfilled
- test_existing_seed_pattern_id_is_preserved
- test_failed_outcome_increments_injection_count_only
- test_abandoned_outcome_increments_injection_count_only
- test_unknown_outcome_increments_injection_count_only
- test_success_outcome_with_injected_id_increments_injection_and_utilization
- test_failed_outcome_does_not_create_new_patterns_from_snippet
- test_success_with_zero_files_edited_updates_metrics_but_does_not_learn
- test_unknown_injected_id_is_skipped_silently
- test_missing_injected_pattern_ids_field_does_not_crash
- test_atomic_write_uses_replace
- test_low_utilization_pattern_is_evicted_after_failed_injections

Adapta tests existentes que llamen write_session_patterns para pasar session_outcome="success" cuando esten probando comportamiento legacy exitoso.

Corre:
.venv/bin/python -m pytest -q tests/test_pattern_writer.py

Reporta:
- Archivos modificados.
- Checklist de comportamiento implementado.
- Tests existentes adaptados.
- Output exacto de pytest.
```

---

## Prompt E — Plan Mode Para Stop Hook

```text
[Usa Plan Mode]

Restore de contexto:
Estamos en /Users/jirustaroure/Desktop/OmniCursor.

Objetivo:
Disenar el cableado final de Option A en .cursor/hooks/scripts/stop.py, sin Option B.

Definicion correcta:
- stop.py debe llamar al writer para cualquier session_outcome.
- El writer decide que hacer:
  - success: metricas + aprendizaje si files_edited > 0.
  - non-success: solo metricas de injected_pattern_ids.
- stdout debe seguir siendo {}.
- send_event y pattern_sync existentes no se convierten en Option B.

Estado actual:
- stop.py solo llama write_session_patterns dentro de:
  if summary["session_outcome"] == "success":
- Eso impide que failed/abandoned/unknown incrementen injection_count.

Exclusiones:
- No tocar .cursor/mcp.json.
- No tocar explanation.md.
- No tocar .cursor/rules/03-omnicursor-ownership.mdc.
- No editar docs viejos.

Disena el cambio sin editar.

Requisitos:
- Cargar events una sola vez si conversation_id existe.
- Llamar write_session_patterns(
    LEARNED_PATTERNS_FILE,
    events,
    summary["files_edited"],
    summary["session_outcome"],
  )
  para cualquier outcome cuando conversation_id exista.
- Mantener la llamada dentro del try/except exterior.
- Mantener recap, send_event y pattern_sync existentes.
- No agregar HTTP POST ni Kafka.

Tests en tests/test_suite_event4_stop.py:
- failed session llama al writer con session_outcome failed.
- abandoned session llama al writer con session_outcome abandoned.
- unknown session llama al writer con session_outcome unknown.
- success path sigue llamando con success.
- sin conversation_id no crashea.
- sin injected_pattern_ids no crashea.

Entrega:
1. Diff textual propuesto del bloque de main().
2. Tests exactos a agregar o adaptar.
3. Riesgos de regresion.

No implementes. Solo plan. Pide confirmacion al final.
```

---

## Prompt F — Implementar Stop Hook

```text
Restore de contexto:
Estamos en /Users/jirustaroure/Desktop/OmniCursor.

Objetivo:
Cablear .cursor/hooks/scripts/stop.py con la nueva API de Option A, sin Option B.

Definicion correcta:
- stop.py debe llamar a write_session_patterns para cualquier outcome.
- success permite aprendizaje + metricas.
- failed/abandoned/unknown solo metricas.
- El detalle de esa semantica vive en pattern_writer.py.

Estado actual:
- stop.py solo llama al writer en success.

Exclusiones:
- No tocar .cursor/mcp.json.
- No tocar explanation.md.
- No tocar .cursor/rules/03-omnicursor-ownership.mdc.
- No editar docs viejos.
- No cambiar emit_client, pattern_sync ni compose.

Implementa:
- Cargar events una vez cuando conversation_id exista.
- Llamar write_session_patterns con session_outcome para cualquier outcome.
- Mantener stdout {}.
- Mantener tolerancia a errores.
- Mantener send_event("onex.evt.omnicursor.session-ended.v1", ...) tal como esta.
- Mantener OMNICURSOR_PATTERN_SYNC_HTTP tal como esta.

Tests:
Actualiza tests/test_suite_event4_stop.py para cubrir:
- test_success_session_calls_writer_with_success
- test_failed_session_calls_writer_for_metrics
- test_abandoned_session_calls_writer_for_metrics
- test_unknown_session_calls_writer_for_metrics
- test_session_without_conversation_id_does_not_call_writer
- test_session_without_injected_ids_does_not_crash

Corre:
.venv/bin/python -m pytest -q tests/test_suite_event4_stop.py tests/test_pattern_writer.py

Reporta:
- Archivos modificados.
- Diff resumido del bloque stop.py.
- Output exacto de pytest.
```

---

## Prompt G — Verificacion Final

```text
Restore de contexto:
Estamos en /Users/jirustaroure/Desktop/OmniCursor.

Objetivo:
Verificar Option A completa. No implementar Option B.

No edites codigo salvo que ruff o tests fallen y el fix sea estrictamente necesario para lo que ya cambiaste.

Exclusiones:
- No tocar .cursor/mcp.json.
- No tocar explanation.md.
- No tocar .cursor/rules/03-omnicursor-ownership.mdc.
- No editar docs viejos.

Ejecuta:
.venv/bin/python -m ruff check src/ tests/ .cursor/hooks/
.venv/bin/python -m pytest -q

Reporta:
1. Archivos modificados.
2. Resumen de comportamiento final de Option A:
   - Donde se loggea injected_pattern_ids.
   - Donde stop.py llama al writer en cualquier outcome.
   - Donde pattern_writer incrementa injection_count en non-success.
   - Donde pattern_writer incrementa utilization_successes solo en success.
   - Donde se hace escritura atomica.
3. Evidencia por tests:
   - Test que prueba failed increments injection_count.
   - Test que prueba failed no increments utilization_successes.
   - Test que prueba backfill de pattern_id.
   - Test que prueba atomic write.
4. Output exacto de ruff.
5. Output exacto de pytest.
6. Pendiente para Option B:
   - Puerto 18091.
   - HTTP write path a intelligence-reducer.
   - Namespace alignment.
   - Emit socket / sidecar.
```

---

## Prompt H — Cierre Documental Opcional

```text
Restore de contexto:
Estamos en /Users/jirustaroure/Desktop/OmniCursor.

Objetivo:
Actualizar solo el documento "INTELLIGENCE_LAYER_CURRENT_STATE_AND_OPTIONS.md" para reflejar que Option A quedo completa, sin tocar Option B ni Option C.

Usa este prompt solo despues de que Prompt G haya pasado ruff y pytest.

Exclusiones:
- No tocar .cursor/mcp.json.
- No tocar explanation.md.
- No tocar .cursor/rules/03-omnicursor-ownership.mdc.
- No tocar otros docs.

Actualiza "INTELLIGENCE_LAYER_CURRENT_STATE_AND_OPTIONS.md":
1. En Option A, agrega una linea de estado:
   STATUS: COMPLETE as of 2026-05-10, verified by ruff + pytest.
2. En "What changes", marca o reformula los bullets para decir que ya esta implementado:
   - injection_count y utilization_successes.
   - tracking por injected_pattern_ids.
   - metricas actualizadas en cualquier outcome.
   - utilization_successes solo en success.
   - atomic write.
3. Mantén el caveat de honestidad:
   - Es proxy de utilizacion, no prueba LLM de que Claude haya usado el texto.
4. No borres "Current Wiring Gaps" de Option B/C.
5. No declares Option B completa.

Corre:
git --no-pager diff "INTELLIGENCE_LAYER_CURRENT_STATE_AND_OPTIONS.md"

Reporta:
- Diff completo del doc.
- Confirmacion de que no tocaste Option B/C salvo aclaraciones necesarias.
```

---

## Senales De Alarma

- Si Claude intenta agregar HTTP, Kafka, Redpanda o intelligence-reducer, detener: eso es Option B/C.
- Si Claude quiere crear patterns nuevas para injected_pattern_ids desconocidos, detener: eso crea fantasmas.
- Si Claude deduplica injected IDs a nivel sesion completo, revisar: injection_count debe contar injections, no solo sesiones.
- Si se rompen tests de success existentes, detener y volver al plan.
- Si `ruff` falla en Prompt G, corregir antes de declarar Option A completa.
- Si `pytest -q` no pasa completo, no pasar a Option B.

