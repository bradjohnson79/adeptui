# Co-Director Reasoning Intelligence Audit

## Architecture Overview

The Co-Director intelligence stack consists of these layers:

```
User Input
  ↓
Intent Classifier (foundation/intent.py — regex-based)
  ↓
Deterministic Router (routing/deterministic.py — regex-based)
  ↓
Context Assembly (conversation/foundation/context_assembler.py)
  ↓
Context Compiler (intelligence/context_compiler.py — budgeted specialist context)
  ↓
Unified Intent Router (routing/unified_intent.py)
  ↓
Provider Selection (service.py — Ollama / hosted / mock)
  ↓
Prompt Construction (prompts/loader.py + system prompt)
  ↓
LLM (Qwen3 / hosted provider)
  ↓
Tool Execution (tools/execution.py)
  ↓
Response Generation + Streaming
  ↓
Enrichment + Momentum + Confidence
```

## Layer Health Assessment

### 1. Intent Classification (foundation/intent.py)
**Verdict: PARTIAL**

The intent classifier uses regex patterns that are reasonably broad but have gaps:

- **COMMAND vs QUESTION distinction**: The `_ACTION_IMPERATIVE_RE` catches "add/change/update/remove/delete/make/put/set..." but these patterns can match conversational phrases as well as commands. There is no explicit "direct imperative command" classifier that distinguishes `"Create Korri's CRS"` (command) from `"Should we create Korri's CRS?"` (question).
- **Vision capability questions**: `"Do you have vision?"` type questions may not match any ACTION/INFORM pattern strongly, falling through to generic modes.
- **Identify-follow-up**: The classifier can detect ACTION intents but may not suppress follow-up suggestions for action commands.

### 2. Deterministic Routing (routing/deterministic.py)
**Verdict: PARTIAL**

The router has dedicated paths for APPROVE, REJECT, NAVIGATE, READ_INSPECT, DISCUSS actions. However:

- `_APPROVE_PATTERN` is very broad (matches "yes", "ok", "sure", "looks good", "do it", "continue", "go ahead").
- `_READ_INSPECT_PATTERN` catches "what", "show me", "inspect", "list" — but a question like "Do you have vision?" may not match `_READ_INSPECT_PATTERN` (no "vision" keyword in the pattern).
- No explicit "answer capability question" route exists — capability questions may fall through to generic response paths.

### 3. Context Assembly (context_assembler.py)
**Verdict: PARTIAL**

The context assembler builds a ranked context block with:
- Project title, mode, active goal, workflow hold, primary intent
- Confirmed facts (top 4)
- Recent messages (last 6)

The block size is reasonable but the ranking may not prioritize current user intent over project context. The instruction "Do NOT inject unrelated production jobs" is present but may not be enforced in all paths.

### 4. Context Compiler (intelligence/context_compiler.py)
**Verdict: HEALTHY**

The compiler uses budgeted, provenance-tagged context compilation. The `FORBIDDEN_CONTEXT_CATEGORIES` block (full_tool_registry, full_marketing_plan) is a good practice. The `USER_MESSAGE_BEGIN/END` delimiters clearly mark the user's message.

### 5. Provider Selection (service.py)
**Verdict: HEALTHY**

Provider selection is deterministic with clear fallback paths. The active provider is determined by env/config, then Ollama, then mock. The provider's capabilities are read from the provider's health check.

### 6. Tool Execution (tools/execution.py)
**Verdict: HEALTHY**

Tools are executed via a structured execution service with capability gating, result sanitization, and invocation tracking.

## Key Findings

### Finding 1: No Explicit "Command vs Question" Distinction
The intent classifier does not distinguish between:
- `"Create Korri's CRS"` (imperative command)
- `"Should we create Korri's CRS?"` (question seeking advice)
- `"What does Korri look like?"` (information question)

All three could match similar patterns and route to the same response mode. The `_ACTION_IMPERATIVE_RE` catches "create" but the `_EXPLAIN_QUESTION_RE/` catches "what/explain" questions. The gap is in the middle — a question phrased as "Should we..." or "Can you..." may not be classified as strongly as a direct imperative.

### Finding 2: Capability Self-Knowledge Is Not Structured
Co-Director's knowledge of its own capabilities (vision, model, tools) comes from the system prompt and context, not from structured runtime data. The model must infer its capabilities from text rather than reading a structured capability object. This leads to:
- Inconsistent vision capability claims
- Inability to distinguish "model supports vision" from "vision is active for this request"
- Hallucinated visual analysis based on project context rather than actual image input

### Finding 3: Vision Attachments Are Handled But Not Self-Reported
The `vision_input.py` module handles image attachment encoding and trace building. However, the model may not receive clear structured information about whether vision was successfully attached for this request. The `is_visual_inspection_turn` function exists but the model's awareness of vision availability depends on prompt context rather than a definitive capability flag.

### Finding 4: Next-Best-Action Layer May Override Context
The conversation momentum and confidence tracking (momentum, confidence) may drive next-best-action suggestions that override the user's explicit current request. The system prompt instructions about "always offer next steps" or "be helpful" could conflict with the "answer the direct question first" principle.

### Finding 5: Clarification Questions Are Not Guarded
There is no explicit policy preventing Co-Director from asking unnecessary clarification questions when sufficient context exists. The intent classifier has no "context_sufficient" check — it doesn't determine whether the current context is sufficient to answer/act, it only classifies the intent.

## Recommended Remediation Priorities

1. **Add structured capability self-knowledge**: Inject a runtime capability object (model, vision_state, attachment_state, tools_available) into the prompt so the model doesn't need to infer these from text.
2. **Strengthen command vs question distinction**: Add explicit COMMAND intent class that routes to ACT rather than DISCUSS.
3. **Add context-sufficiency check**: Before asking a question, check whether the required parameters are resolvable from current context.
4. **Suppress next-best-action during commands**: When a direct production command is detected, disable suggestion/next-step layers.
5. **Add "vision active for this request" flag**: The model should receive a definitive "vision_active: true/false" signal for each turn.

## Files Referenced

- studio-api/app/codirector/conversation/foundation/intent.py — Intent classification
- studio-api/app/codirector/routing/deterministic.py — Deterministic routing
- studio-api/app/codirector/service.py — Chat orchestration
- studio-api/app/codirector/conversation/foundation/context_assembler.py — Context assembly
- studio-api/app/codirector/intelligence/context_compiler.py — Context compilation
- studio-api/app/codirector/vision_input.py — Vision handling
- studio-api/app/codirector/tools/execution.py — Tool execution
- studio-api/app/codirector/prompts/loader.py — Prompt loading
- studio-api/app/codirector/routing/unified_intent.py — Unified intent routing
