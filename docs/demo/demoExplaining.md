# demoExplaining.md — La demo A+B explicada en cristiano

> Pensado para alguien que abre el repo por primera vez y dice "¿qué es esto y por qué debería importarme?". Sin jerga, con analogías. Cuando aparece un término técnico, va con una traducción al lado.

---

## 1. ¿Qué es OmniCursor en una frase?

**OmniCursor convierte el editor Cursor en un asistente con memoria local que aprende de cómo trabajas, sin depender de servidores en la nube.**

Cursor solo es la silla. OmniCursor es el cinturón, el airbag, el GPS y la libreta donde apuntas lo que aprendiste de cada viaje.

---

## 2. ¿Qué demuestra esta demo concretamente?

Que el sistema hace **5 cosas útiles, todas en tu máquina, sin Docker, sin Kafka, sin red:**

1. Entiende de qué va tu pregunta y elige automáticamente el "perfil" de agente correcto.
2. Cuando editas un archivo Python, le pasa un revisor de calidad por encima (`ruff`).
3. Recuerda patrones entre sesiones (lo que aprendió ayer, lo usa hoy).
4. Cuando cierras la sesión, deja un "tique" estructurado en una carpeta. Ese tique es el contrato que mañana subirá a un sistema más grande (OmniIntelligence).
5. Si apagas los "hooks" (los automatismos), el puente al backend de tools sigue funcionando. Dos caminos independientes, ninguno dependiente del otro.

---

## 3. Los actores (la analogía importante)

Imagina una **oficina pequeña**:

| Personaje | Quién es en el código | Qué hace |
|---|---|---|
| **Recepcionista** | `user-prompt-submit.py` (hook `beforeSubmitPrompt`) | Cada vez que tú dices algo, lee tu mensaje y decide a qué especialista de la oficina mandarlo. |
| **Corrector** | `post-edit.py` (hook `afterFileEdit`) | Cada vez que se modifica un archivo, le pasa la regla por encima (`ruff` para Python). No corrige por ti, solo te dice qué está mal. |
| **Secretario de cierre** | `stop.py` (hook `stop`) | Cuando se acaba la reunión, escribe un acta resumen (a quién atendiste, cuántos archivos tocaste, qué patrones se usaron) y la mete en un cajón llamado *outbox*. |
| **Libreta de hábitos** | `~/.omnicursor/learned_patterns.json` | Donde guardas qué tipo de pregunta tiende a aparecer y qué funcionó la última vez. |
| **Cajón de actas** | `~/.omnicursor/outbox.jsonl` | Donde se acumulan las actas para que luego alguien las suba a la sede central. |
| **Diario de bordo** | `~/.omnicursor/events.jsonl` | Cada cosa que pasa en la oficina queda apuntada aquí, en orden. |
| **Puente al almacén** | `omnimarket_bridge` (MCP) | Un teléfono directo al almacén (OmniMarket) para pedir herramientas grandes sin pasar por los hooks. |

> Si esto no fuera un editor, sería: un consultorio médico que toma nota de cada paciente, asigna automáticamente el especialista, revisa la receta antes de entregarla, y al final del día deja un sobre con el resumen para enviar al hospital central.

---

## 4. Antes de la demo: el setup

Lo "necesario" en tu máquina:

- Repo en `/path/to/OmniCursor`
- Rama `julian/option-b-from-main`
- Un entorno Python local `.venv` con dos cosas dentro: `ruff` (el corrector) y `mcp` (la librería del puente).
- Una carpeta local de OmniMarket (`omnimarket/`) — el "almacén".

Lo "agradable de tener":
- `jq` para mirar los eventos en JSON cómodamente.

Lo "innecesario":
- **Docker no hace falta**. Esto es lo importante de la demo: todo corre en tu portátil sin levantar contenedores.

Antes de empezar haces tres cosas:
1. **Backup** de los tres archivos de estado (`events.jsonl`, `outbox.jsonl`, `learned_patterns.json`). Por si la cagas, puedes volver.
2. Defines una variable `OMNICURSOR_OUTBOX_FILE` apuntando a un outbox **separado** (`demo-outbox.jsonl`). Así no mezclas el ruido de la demo con tu histórico.
3. Compruebas que el sistema arranca verde: `pytest` pasa los 599 tests, `ruff` está limpio, y el puente al almacén responde `ok: true`.

---

## 5. Los 5 escenarios, uno por uno

En lo que sigue uso esta convención:
- **Entrada:** lo que tú haces.
- **Lo que pasa por dentro:** la maquinaria invisible.
- **Salida esperada:** la prueba de que funcionó.
- **Lo que vimos en la corrida real:** lo que de verdad pasó cuando lo ejecuté.

---

### Escenario 1 — "Adivina qué quiero"

**Entrada:**
Tú escribes en Cursor algo como:

> "Debug why pattern_sync should never overwrite learned_patterns.json…"

**Lo que pasa por dentro:**
El recepcionista intercepta tu frase **antes** de que el modelo responda. Pasa tu texto por tres tamices, en orden:

1. ¿Hay alguna palabra que coincide *exacto* con un trigger conocido? (ej. "debug", "summarize", "review PR")
2. Si no, ¿hay alguna palabra *parecida* (fuzzy match)?
3. Si no, ¿cuántas palabras de tu mensaje se solapan con las palabras clave de cada agente?

Le da un score 0–1. Si supera 0.55, ese agente gana. Si no, va al genérico ("polymorphic-agent").

**Salida esperada:**
Una línea en `events.jsonl` así:
```json
{ "event": "prompt_classified",
  "matched_agent": "debug-intelligence",
  "score": 0.95,
  "patterns_injected": 2,
  "injected_pattern_ids": ["..."] }
```

**Lo que vimos en la corrida real:**
- El agente que ganó **no fue** `debug-intelligence`, fue `content-summarizer`, con 0.95.
- ¿Por qué? Porque en el prompt aparecía la palabra **"summarize"** ("summarize the evidence"), y eso es un trigger exacto de `content-summarizer`. El tamiz 1 lo capturó antes de llegar al 2 o al 3.
- **Hallazgo real:** el prompt de ejemplo del runbook tiene un bug. Si quieres que gane `debug-intelligence`, no debes decir "summarize" en la frase. Cámbialo por "investigate" o "explain".

**Por qué importa esto:**
Demuestra que **no se llama a ninguna API externa para clasificar**. Todo el ranking pasa en 1 milisegundo, en tu CPU, leyendo un archivo JSON con la definición de cada agente. Es la pieza más barata y más útil del sistema.

---

### Escenario 2 — "Cuando editas, te reviso"

**Entrada:**
Tú (o el modelo) crea un archivo Python con un error obvio, por ejemplo un `import os` que no se usa.

**Lo que pasa por dentro:**
El corrector se activa después del edit. Detecta que la extensión es `.py`, lanza `ruff check` sobre el archivo, cuenta cuántas líneas no vacías salieron de la salida, y deja constancia.

**Importante:** no corrige nada. **Solo reporta.** Es un detector de humo, no el bombero.

**Salida esperada:**
```json
{ "event": "file_edited",
  "file_path": "eval/demo_autolint.py",
  "language": "python",
  "ruff_findings": 1 }
```

**Lo que vimos en la corrida real:**
- La primera invocación dio `ruff_findings: 0`. Cero. Como si no hubiera errores.
- ¿Por qué? Porque el hook llama a `ruff` sin path absoluto, y en el shell donde lo ejecuté, `ruff` no estaba en el `PATH` (solo está en `.venv/bin/ruff`). El subprocess murió con `FileNotFoundError` y se lo tragó silencioso.
- Repetí la invocación añadiendo `.venv/bin` al `PATH` → `ruff_findings: 11`. Funcionó.
- **Hallazgo real:** este es un bug latente. Si en la demo en vivo Cursor lanza el hook sin `.venv/bin` en el PATH, vas a ver `0` en cámara y la demo pierde gracia. La solución es que el código del hook use `shutil.which("ruff")` o `python -m ruff` para no depender del PATH.

**Por qué importa esto:**
Demuestra que cada vez que tu agente toca un archivo Python, hay un **gate de calidad automático** que te avisa de problemas. Es como tener un compañero senior leyendo cada diff sin pedírselo.

---

### Escenario 3 — "Recuerdo lo de ayer"

**Entrada:**
Antes de la sesión, "plantas" un patrón a mano en `learned_patterns.json`:

```json
{ "pattern_id": "demo-pattern-omnicursor-preserve-marker",
  "domain": "debug_intelligence",
  "keywords": ["demo_marker", "pattern_sync", "learned_patterns"],
  "description": "...",
  "weight": 1.0,
  "injection_count": 0,
  "utilization_successes": 0 }
```

Esto es como meterle al asistente un post-it que dice "oye, cuando veas estas palabras, recuerda esta lección".

Luego, en una **nueva sesión** (otro `conversation_id`), escribes:

> "Debug this demo workflow: when editing files that contain DEMO_MARKER, preserve that marker… Finish with done."

**Lo que pasa por dentro:**
El recepcionista clasifica el prompt como `debug-intelligence` (esta vez sí, porque no hay "summarize"). Antes de enviar contexto al modelo, mira en la libreta de patrones del dominio `debug_intelligence`, los filtra por relevancia (qué tan similares son al prompt actual), y **inyecta los relevantes en el system message** que ve el modelo.

**Salida esperada:**
```json
{ "matched_agent": "debug-intelligence",
  "patterns_injected": 2,
  "injected_pattern_ids": [
    "auto-...",
    "demo-pattern-omnicursor-preserve-marker"
  ] }
```

**Lo que vimos en la corrida real:**
- Exactamente eso. El patrón plantado apareció en `injected_pattern_ids` junto a otro patrón auto-aprendido (`auto-20bb53eead64`).
- El `injection_count` del patrón **no se actualizó todavía** (seguía en 0). Eso pasa al cerrar la sesión, no al inyectar.

**Por qué importa esto:**
Demuestra **memoria que sobrevive entre sesiones**. Es la diferencia entre un asistente que olvida cada conversación y uno que va acumulando intuiciones. Sin servidores, sin login, todo en un JSON local.

---

### Escenario 4 — "Cuando cierras, dejo el sobre"

**Entrada:**
Tú cierras la sesión en Cursor (cierras el chat). Esto dispara el hook `stop`.

**Lo que pasa por dentro:**
El secretario de cierre hace cinco cosas, en orden:

1. **Recoge** todos los eventos de esta `conversation_id` del diario de bordo.
2. **Clasifica el resultado** con un árbol de 4 puertas: ¿hubo error? → `failed`. ¿Hubo trabajo + marcador de "done"? → `success`. ¿Sesión cortita y sin marcador? → `abandoned`. Cualquier otra cosa → `unknown`.
3. **Actualiza la libreta de patrones**: a los patrones que se usaron en una sesión `success` con archivos editados, les sube `injection_count` y `utilization_successes`. Esto es la pieza de **Option A — pattern utilization tracking**.
4. **Escribe un acta estructurada** en el outbox.
5. (Opcional, si está habilitado por env var) Intenta sincronizar con OmniIntelligence remoto.

**Salida esperada:**
Una línea JSON en `~/.omnicursor/demo-outbox.jsonl` con esta forma:

```json
{ "schema_version": "omnicursor.session_outcome.v1",
  "source": "omnicursor",
  "conversation_id": "...",
  "correlation_id": "...",
  "started_at": "...",
  "ended_at": "...",
  "session_outcome": "success",
  "prompts_classified": 1,
  "files_edited": 1,
  "matched_agent": "debug-intelligence",
  "matched_confidence": 0.95,
  "patterns_injected": 2,
  "injected_pattern_ids": ["...", "demo-pattern-..."],
  "languages": ["python"],
  "shell_commands": { "allowed": 0, "denied": 0, "warned": 0 } }
```

**Lo que vimos en la corrida real:**
- Salió **exactamente** ese payload. Todos los campos del schema v1.
- Verifiqué que el `injection_count` del patrón plantado subió de **0 → 1** y `utilization_successes` de **0 → 1**, con `weight: 1.0 → 0.95` (hay un decay aplicado).
- El `correlation_id` del outbox coincide con el `correlation_id` del `prompt_classified` de hace 18 segundos. **La trazabilidad por prompt funciona.**

**Por qué importa esto:**
Este sobre es **el contrato congelado**. Cuando llegue Option C (la integración con Kafka y OmniIntelligence), nadie tiene que reescribir nada. Solo cambia "dónde se deposita el sobre": en lugar de en un archivo local, va a un broker Kafka. Los campos están diseñados para que el sistema upstream los consuma directamente, sin traducción. Es la promesa de "local-first, remote-ready".

> **Detalle honesto:** según `docs/archive/dev/handoffs/2026-05-10-option-a-handoff.md`, hay gaps abiertos en Option A: los outcomes `failed`, `abandoned` y `unknown` aún **no** actualizan `injection_count` (solo `success` lo hace), y la escritura del JSON no es atómica. Esto no se ve en la demo porque ejecutamos un happy path, pero son los próximos parches.

---

### Escenario 5 — "Sin hooks también funciona"

**Entrada:**
Apagas los hooks en Cursor (Settings → Features → Hooks → off) y luego pides al modelo que use la herramienta MCP `run_local_review`.

**Lo que pasa por dentro:**
El MCP server (`omnicursor.mcp.omnimarket_bridge_server`) recibe la llamada, invoca el bridge, que a su vez lanza un subprocess `python -m omnimarket.nodes.node_local_review --dry-run` en la carpeta `omnimarket/`, captura el JSON resultante y lo devuelve.

Los hooks no participan en absoluto. Son dos caminos paralelos.

**Salida esperada:**
```json
{ "ok": true,
  "returncode": 0,
  "state": { "current_phase": "init", "dry_run": true, ... } }
```

**Lo que vimos en la corrida real:**
- El smoke por shell pasó: `ok: true`, `returncode: 0`, `current_phase: init`, `dry_run: true`.
- La parte de "apagar hooks desde Cursor UI y llamar al MCP desde Cursor" **no se puede automatizar desde aquí** (no tengo control de la UI). En la demo en vivo lo demuestras tú a mano: toggle off, llamar la tool, ver `"ok": true`, toggle on.

**Por qué importa esto:**
Es la prueba de **resiliencia arquitectónica**. Si los hooks fallan, el sistema sigue siendo útil vía MCP. Si el MCP falla, los hooks siguen funcionando para clasificar y aprender. Ningún componente es punto único de fallo.

---

## 6. Resumen visual de qué pasa, en orden

```
TÚ ESCRIBES UN PROMPT
        │
        ▼
┌─────────────────────────────────┐
│ Hook beforeSubmitPrompt         │
│ - Clasifica → agente + score    │
│ - Inyecta patrones relevantes   │
│ - Escribe events.jsonl          │
└─────────────────────────────────┘
        │
        ▼
   EL MODELO RESPONDE
        │
        │ (si el modelo edita archivos)
        ▼
┌─────────────────────────────────┐
│ Hook afterFileEdit              │
│ - Detecta lenguaje              │
│ - Corre ruff diagnóstico        │
│ - Escribe events.jsonl          │
└─────────────────────────────────┘
        │
        ▼
   TÚ CIERRAS EL CHAT
        │
        ▼
┌─────────────────────────────────┐
│ Hook stop                       │
│ - Aggrega eventos de la sesión  │
│ - Clasifica outcome             │
│ - Actualiza learned_patterns    │
│ - Escribe outbox.jsonl (acta)   │
└─────────────────────────────────┘
        │
        ▼
   ACTA EN OUTBOX
   (lista para drenar a Kafka)


  PARALELO E INDEPENDIENTE:
   TÚ (o el modelo) llama MCP run_local_review
        │
        ▼
   Bridge → subprocess → omnimarket → JSON → de vuelta
```

---

## 7. Cosas raras que vimos en la corrida real

| Síntoma | Causa | Severidad |
|---|---|---|
| Escenario 1 eligió `content-summarizer` en lugar de `debug-intelligence` | El prompt-ejemplo del runbook contiene "summarize", trigger exacto de otro agente | **MEDIA** — corregir el prompt-ejemplo del runbook |
| Escenario 2 dio `ruff_findings: 0` en la primera invocación | El hook llama `ruff` sin path absoluto; `.venv/bin` no estaba en el PATH del shell | **ALTA** — bug latente que muerde en la demo en vivo si Cursor no exporta el PATH correcto |
| `injection_count` del patrón seguía en 0 después de inyectarse | El contador se actualiza en `stop`, no en `prompt_classified`. Es el diseño correcto. | **BAJA** — solo confunde si esperas updates en tiempo real |
| Los gaps de Option A documentados en `docs/archive/dev/handoffs/2026-05-10-option-a-handoff.md` no se vieron | La demo es happy path (`success`); los gaps están en outcomes `failed/abandoned/unknown` | **BAJA** — esperado, no es un bug |

---

## 8. Si nada de esto te suena, esta es la idea de fondo

1. **OmniCursor no es un modelo de IA.** Es una capa de plomería local que rodea a Cursor.
2. **Su trabajo es: capturar lo que pasa, decidir cosas baratas localmente, dejar un rastro estructurado para que el sistema grande (OmniIntelligence) lo consuma después.**
3. **No depende de la nube para funcionar.** Si te quedas sin internet, las 5 cosas siguen pasando.
4. **El outbox es el contrato.** Es el único punto donde el mundo local toca el mundo remoto. Hoy escribe en un archivo. Mañana en Kafka. El payload es el mismo.
5. **Los hooks son lifecycle scripts deterministas.** No tienen LLM dentro. No piensan. Solo siguen reglas claras y rápidas.

Si tuvieras que vender esto en 30 segundos:

> "Cursor es un editor con IA. OmniCursor lo convierte en un sistema con memoria, gates de calidad automáticos y un rastro auditable de cada sesión, todo offline. Cuando llegue el momento de conectarlo a infraestructura mayor, ya está listo: el contrato está congelado, los campos están escogidos, y nada en el flujo local cambia."

---

## 9. Glosario mínimo

- **Hook:** un script que Cursor ejecuta automáticamente en ciertos momentos (antes de enviar un prompt, después de editar un archivo, al cerrar la sesión, antes de correr un comando de shell).
- **MCP:** "Model Context Protocol". Una forma estándar de que el modelo invoque herramientas externas. Aquí lo usamos para que el modelo pueda pedir cosas a OmniMarket.
- **Outbox:** un archivo donde se acumulan mensajes que algún día se subirán a otro sitio. Es la cola local.
- **Schema v1 (`omnicursor.session_outcome.v1`):** la forma fija que tiene cada acta. No puede cambiar sin romper a quien la consuma.
- **Pattern injection:** meter en el system message del modelo recordatorios de cosas que funcionaron en el pasado.
- **Option A / Option B / Option C:** fases del plan. A = pattern utilization. B = outbox durable. C = integrar con OmniIntelligence remoto.
- **OmniMarket:** repo hermano que aloja "nodos" — piezas de lógica de negocio reutilizable. OmniCursor solo llama, no implementa.

---

## 10. Cómo replicar la demo tú mismo en 30 segundos

```bash
cd /path/to/OmniCursor

# 1. Verifica que arranca verde
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check src/ tests/ .cursor/hooks/

# 2. Bridge smoke
OMNIMARKET_ROOT=/path/to/omnimarket \
  PYTHONPATH=src .venv/bin/python -c "
import json
from omnicursor.omnimarket_bridge import run_local_review
print(json.dumps(run_local_review(dry_run=True), indent=2, default=str))
"
# Esperado: "ok": true

# 3. Mira los últimos eventos
tail -n 20 ~/.omnicursor/events.jsonl | jq -c '.event'

# 4. Mira el outbox (si has cerrado al menos una sesión hoy)
tail -n 1 ~/.omnicursor/outbox.jsonl | jq .
```

Si los cuatro pasos pasan, la demo está sana.

---

**Última actualización:** 2026-05-10  
**Basado en:** corrida real ejecutada antes de escribir este doc; ver [`demo_runbook_ab.md`](./demo_runbook_ab.md) para los comandos exactos del runbook formal.
