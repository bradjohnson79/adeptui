"""Dialogue policy â€” sole authority for creator-facing behavior."""

from __future__ import annotations

from .schemas import (
    CoDirectorMode,
    ConversationState,
    DialoguePlan,
    IntentAnalysis,
    IntentType,
    InteractionPosture,
)

_TITLE_PREMISE_PROHIBITIONS = [
    "Demand a title",
    "Demand a one-sentence premise",
    "Start a questionnaire",
    "Begin production planning",
    "Pretend to know facts not yet shared",
    "Ask for genre, logline, or structured intake fields",
]


def build_dialogue_plan(
    intent: IntentAnalysis,
    state: ConversationState | None = None,
) -> DialoguePlan:
    """Map intent (+ conversation state) to an authoritative DialoguePlan."""

    state = state or ConversationState()
    # Preference to explain before production must not trap later authorized plan/execute turns.
    action_release = intent.primary_intent in {
        IntentType.REQUEST_ACTION,
        IntentType.REQUEST_PLAN,
        IntentType.REQUEST_GENERATION,
        IntentType.REQUEST_FEEDBACK,
    }
    hold = (state.workflow_hold or state.preference_explain_before_production) and not action_release

    if intent.primary_intent == IntentType.EXPLAIN_PROJECT or (
        IntentType.EXPLAIN_PROJECT in intent.secondary_intents and InteractionPosture.LISTEN in intent.required_postures
    ):
        return DialoguePlan(
            posture=[InteractionPosture.LISTEN, InteractionPosture.ACKNOWLEDGE],
            response_purpose=(
                "Welcome the user's project explanation and signal attentive listening "
                "without forcing structure."
            ),
            required_elements=[
                "Confirm that explaining the story first is a sensible approach",
                "Express specific interest in learning the project the user named or described",
                "State that Co-Director will listen for story, characters, rules, tone, and continuity",
                "Invite the user to begin in their own way",
            ],
            prohibited_elements=list(_TITLE_PREMISE_PROHIBITIONS),
            question_budget=0,
            tool_policy="NONE",
            memory_policy="WRITE_CONFIRMED_FACTS",
            workflow_advance_policy="HOLD",
            tone_profile="attentive-warm",
            mode=CoDirectorMode.LISTENING,
        )

    if intent.primary_intent in {IntentType.PAUSE_ACTION, IntentType.SET_PREFERENCE} or (
        hold and not action_release
    ):
        if InteractionPosture.LISTEN in intent.required_postures or hold:
            return DialoguePlan(
                posture=[InteractionPosture.LISTEN, InteractionPosture.ACKNOWLEDGE],
                response_purpose="Acknowledge the instruction to keep listening / hold planning.",
                required_elements=[
                    "Acknowledge the user's instruction",
                    "Confirm planning/questions will wait",
                ],
                prohibited_elements=list(_TITLE_PREMISE_PROHIBITIONS) + ["Ask a new question"],
                question_budget=0,
                tool_policy="NONE",
                memory_policy="WRITE_CONFIRMED_FACTS",
                workflow_advance_policy="HOLD",
                tone_profile="attentive-warm",
                mode=CoDirectorMode.LISTENING,
            )

    if intent.primary_intent == IntentType.CORRECT_ASSISTANT:
        return DialoguePlan(
            posture=[InteractionPosture.APOLOGIZE_AND_CORRECT, InteractionPosture.ACKNOWLEDGE],
            response_purpose="Acknowledge the correction and update understanding.",
            required_elements=["Acknowledge the specific correction", "Restate corrected understanding briefly"],
            prohibited_elements=["Defend the previous mistake", "Start a questionnaire"],
            question_budget=0,
            tool_policy="NONE",
            memory_policy="WRITE_CONFIRMED_FACTS",
            workflow_advance_policy="HOLD",
            tone_profile="direct-respectful",
            mode=CoDirectorMode.DISCOVERY,
        )

    if intent.primary_intent == IntentType.EXPRESS_DISSATISFACTION:
        return DialoguePlan(
            posture=[InteractionPosture.APOLOGIZE_AND_CORRECT, InteractionPosture.LISTEN],
            response_purpose="Acknowledge failure and realign to the user's intent.",
            required_elements=["Acknowledge the failure without defensiveness", "Restate the user's actual intent"],
            prohibited_elements=list(_TITLE_PREMISE_PROHIBITIONS),
            question_budget=0,
            tool_policy="NONE",
            memory_policy="WRITE_CONFIRMED_FACTS",
            workflow_advance_policy="HOLD",
            tone_profile="direct-respectful",
            mode=CoDirectorMode.LISTENING,
        )

    if intent.primary_intent == IntentType.RECALL_SCENE:
        # Final-closure mission 2026-09-19 (Blockers 1+2): exact scene-state
        # recall/summary. The answer must be complete (every established
        # active fact) and strictly faithful (nothing unstated).
        return DialoguePlan(
            posture=[InteractionPosture.REVIEW, InteractionPosture.ADVISE],
            response_purpose="Recall the current scene exactly from established facts — complete and faithful.",
            required_elements=[
                "Use ONLY facts explicitly established in this conversation or in active scene/project state",
                "Enumerate every established active fact: each character with their role/action, each stated position or blocking, each prop, the setting/background, any stated audio, and any stated camera/framing",
                "Include the project/deliverable framing the creator stated (e.g. what the piece is — an ad, a short, a scene — and its format) exactly as established",
                "Include established-but-unseen elements (e.g. an offscreen voice) when the question covers the scene",
                "If a fact was corrected later, state only the corrected version",
                "If something was never established, say so instead of filling the gap",
            ],
            prohibited_elements=list(_TITLE_PREMISE_PROHIBITIONS) + [
                "Invent staging, positions, actions, or details that were never stated or approved",
                "Omit an established active fact from the recall",
                "Turn the recall into suggestions, next steps, or new creative material",
            ],
            question_budget=0,
            tool_policy="NONE",
            memory_policy="NONE",
            workflow_advance_policy="SUGGEST",
            tone_profile="production-clear",
            mode=CoDirectorMode.REVIEW,
        )

    if intent.primary_intent == IntentType.PROMPT_AUTHORING:
        # Intelligence mission 2026-09-19 (Phase 5): the creator asked FOR the
        # prompt text (timed prompt / shot prompt / prompt draft). Co-Director
        # writes the prompt itself — grounded in the current scene and
        # production context — instead of dispatching a job or refusing.
        return DialoguePlan(
            posture=[InteractionPosture.CREATE, InteractionPosture.ADVISE],
            response_purpose="Write the requested prompt text directly, grounded in the current scene and production context.",
            required_elements=[
                "Write the actual prompt text the creator asked for",
                "Ground the prompt in the established scene state (characters, blocking, camera, audio, restrictions)",
                "Honor any explicit restrictions from the conversation (e.g. do not generate yet)",
            ],
            prohibited_elements=list(_TITLE_PREMISE_PROHIBITIONS) + [
                "Dispatch a generation job when the creator only asked for the text",
                "Refuse or defer the prompt-writing task",
                "List runner parameters (steps, guidance, CFG) as the fulfillment",
            ],
            question_budget=0,
            tool_policy="NONE",
            memory_policy="NONE",
            workflow_advance_policy="SUGGEST",
            tone_profile="production-clear",
            mode=CoDirectorMode.PLANNING,
        )

    if intent.primary_intent == IntentType.REQUEST_FEEDBACK:
        return DialoguePlan(
            posture=[InteractionPosture.REVIEW, InteractionPosture.ADVISE],
            response_purpose="Provide honest, constructive feedback.",
            required_elements=["Separate strengths, risks, and suggestions", "Respect creator ownership"],
            prohibited_elements=["Empty praise", "Automatic agreement"],
            question_budget=0,
            tool_policy="NONE",
            memory_policy="NONE",
            workflow_advance_policy="SUGGEST",
            tone_profile="candid-supportive",
            mode=CoDirectorMode.REVIEW,
        )

    if intent.primary_intent == IntentType.REQUEST_PLAN:
        return DialoguePlan(
            posture=[InteractionPosture.ADVISE, InteractionPosture.PLAN],
            response_purpose="Recommend a focused next step.",
            required_elements=["Offer a clear next step grounded in current context"],
            prohibited_elements=["Launch an unrelated multi-field questionnaire"],
            question_budget=1 if intent.should_ask_question else 0,
            tool_policy="NONE",
            memory_policy="NONE",
            workflow_advance_policy="SUGGEST",
            tone_profile="production-clear",
            mode=CoDirectorMode.PLANNING,
        )

    if intent.primary_intent in {IntentType.REQUEST_ACTION, IntentType.REQUEST_GENERATION}:
        return DialoguePlan(
            posture=[InteractionPosture.EXECUTE],
            response_purpose="Proceed with authorized action using inherited context.",
            required_elements=["Acknowledge the action concisely before executing"],
            prohibited_elements=[
                "Silent execution without authorization",
                "Ask unnecessary clarifying questions when the brief is sufficient",
                "Give the creator a prompt to paste or run themselves",
                "List runner parameters (steps, guidance, CFG) as the fulfillment",
                "Tell the creator to run this locally or paste into Flux",
                "Ask what consequence follows when a world rule is broken",
            ],
            question_budget=0,
            tool_policy="OPTIONAL",
            memory_policy="NONE",
            workflow_advance_policy="ADVANCE",
            tone_profile="production-clear",
            mode=CoDirectorMode.EXECUTION,
        )

    if intent.primary_intent == IntentType.INFORM:
        return DialoguePlan(
            posture=[InteractionPosture.LISTEN, InteractionPosture.ACKNOWLEDGE],
            response_purpose="Acknowledge new information and track it without interrupting.",
            required_elements=["Reflect something specific from what was just shared"],
            prohibited_elements=list(_TITLE_PREMISE_PROHIBITIONS),
            question_budget=0,
            tool_policy="NONE",
            memory_policy="WRITE_CONFIRMED_FACTS" if intent.should_write_memory else "PROPOSE",
            workflow_advance_policy="HOLD" if hold else "SUGGEST",
            tone_profile="attentive-warm",
            mode=CoDirectorMode.LISTENING if hold else CoDirectorMode.DISCOVERY,
        )

    return DialoguePlan(
        posture=list(intent.required_postures) or [InteractionPosture.ACKNOWLEDGE],
        response_purpose="Continue the conversation helpfully.",
        required_elements=["Address the latest user message"],
        prohibited_elements=["Ignore the latest message"],
        question_budget=1 if intent.should_ask_question else 0,
        tool_policy="OPTIONAL" if intent.should_use_tools else "NONE",
        memory_policy="NONE",
        workflow_advance_policy="SUGGEST",
        tone_profile="attentive-warm",
        mode=CoDirectorMode.DISCOVERY,
    )
