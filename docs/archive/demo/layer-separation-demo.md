# Layer Separation Demo Script

Walk through this live in Cursor to prove rules, hooks, and skills are distinct layers.

---

## The Prompt to Use

```
I have a TypeError on line 42 in my parser. Help me debug it.
```

---

## Step 1: Show the Rule Firing (background knowledge injection)

**What to point to:** `.cursor/rules/00-omninode-concepts.mdc`

This rule has `alwaysApply: true` — Cursor loads it into every session automatically.
It injects OmniNode vocabulary (node types, bucket classifications, skill paths) before
the model sees any prompt.

**What to say:** "This is the rules layer. It fires always, regardless of what the user types.
The model already has this context before I submit my prompt."

---

## Step 2: Show the Hook Firing (automatic routing)

**What to point to:** `.cursor/hooks.json` → `beforeSubmitPrompt` → `on_prompt.py`

When you submit the debugging prompt, `on_prompt.py` fires before the model responds.
It classifies the prompt and injects a `systemMessage` like:

```
<!-- OmniCursor: agent=debug-intelligence confidence=0.95 -->
**Routing:** debug-intelligence agent selected (score: 0.95)
Reason: Exact trigger: 'error'
**Recommended skill:** `/systematic-debugging`
```

**What to say:** "This is the hooks layer. It ran deterministically before the LLM saw
the prompt. No LLM was involved in the routing decision — it's pure pattern matching in Python.
The model now knows which agent it is and which skill to follow."

**To prove it happened before the model responded:** show `~/.omnicursor/events.jsonl` — the
`prompt_classified` event is written before the model's first token.

---

## Step 3: Show the Skill Being Read (methodology on demand)

**What to point to:** `skills/systematic-debugging.md`

The routing hint told the model to use `/systematic-debugging`. The model opens
`skills/systematic-debugging.md` and follows the 5-phase methodology:
1. Backward Tracing — trace the call chain backward to the original trigger
2. Root Cause Investigation — read errors carefully, reproduce consistently
3. Pattern Analysis — find working examples, compare against broken code
4. Hypothesis and Testing — form one hypothesis, test minimally
5. Implementation — fix the root cause, write failing test first

**What to say:** "This is the skills layer. It's a Markdown document — not code.
The LLM is the runtime. It reads the methodology and applies it to the specific problem."

---

## Step 4: Remove One Layer and Show Degradation

**Disable hooks:** rename `.cursor/hooks.json` to `.cursor/hooks.json.bak`

Submit the same prompt. What changes:
- The routing hint is gone — the model doesn't know to use debug-intelligence persona
- The `systemMessage` is absent — no confidence score, no skill recommendation
- The model still has rules (00-omninode-concepts) and can still open skills manually
- But the automatic "you are a debugging agent, follow systematic-debugging" is gone

**What to say:** "Rules and skills still work, but the automatic pre-prompt routing
disappears. The model has to figure out what to do on its own, which is less reliable
and less specialized."

Rename back: `.cursor/hooks.json.bak` → `.cursor/hooks.json`

---

## Step 5: Answer the Key Question

**Why can't the hook replace the skill file (or vice versa)?**

The hook fires automatically and deterministically — it runs Python code before the LLM sees anything.
It's infrastructure. It cannot contain 200 lines of debugging methodology because it doesn't
have an LLM to read and apply that methodology.

The skill file is methodology content — it tells the LLM *how to think* about a problem.
It can't fire automatically because reading it requires an LLM.

**They serve different purposes:** hooks shape behavior deterministically before inference;
skills shape reasoning during inference.

---

## Checklist

- [ ] Show `00-omninode-concepts.mdc` with `alwaysApply: true`
- [ ] Submit debugging prompt, show `systemMessage` in Cursor context
- [ ] Open `~/.omnicursor/events.jsonl`, point to `prompt_classified` event timestamp
- [ ] Open `skills/systematic-debugging.md`, show the 5-phase structure
- [ ] Rename `hooks.json`, submit same prompt, show degradation
- [ ] Rename back, explain why hooks ≠ skills
