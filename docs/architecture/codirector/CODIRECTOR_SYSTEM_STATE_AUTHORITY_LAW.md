# Co-Director System-State Authority Law

Canonical standing law. Conversation may remember intent. It is never proof of what Adept UI contains or has completed.

Always-on Cursor rule: `.cursor/rules/codirector-system-state-authority.mdc`

This mission records the law and certifies the first instance (Timed Prompt / Timeline store). Other subsystems inherit the law on their next authorized mission. Do not “finish the examples” by rewriting Creators, Library, Voice, jobs, Comfy, or MiniMax here.

## Three things that are not equivalent

- **USER INTENT** — what the creator asked for
- **CONVERSATIONAL MEMORY** — what was said, drafted, or previously claimed
- **SYSTEM STATE** — what the owning store actually holds right now

## Authority order (state-sensitive claims)

```
SYSTEM STATE
>
VERIFIED TOOL RESULT
>
CONVERSATIONAL HISTORY
```

Conversation history may help remember goals, drafts, preferences, corrections, referents, and unresolved intent. It must never be the final authority for whether a tool executed, data persisted, a reference exists, a job is active, generation completed, an asset is saved, or a setting changed.

## Applies to every Adept UI system

Timeline, Library, Character Creator, Prop Creator, Environment Creator, Voice Creator, Voice Studio, Audio Studio, Projects, global assets, local project assets, references, Timed Prompts, Direct References, scene state, render queue, video/image/audio generation, jobs, Comfy workflows, MiniMax jobs, model/provider state, files/assets, Co-Director production state, and any future module.

Examples (epistemology):

- Conversation: “I added the Timed Prompt.” Timeline empty → not populated
- Conversation: “Korri is global.” Registry `global = false` → not global
- Conversation: “I added @Cade.” Scene References lacks Cade’s asset ID → not attached
- Conversation: “The video is generating.” Render Queue `active = 0` → not underway
- Conversation: “Generation completed.” Job store `FAILED` → report the failure
- Conversation: “That image is in the project Library.” No asset ID → not in Library
- Conversation: “Cade has this voice assigned.” No assignment → unassigned

## Read-before-claim

Before any factual claim such as “I added / I saved / it is now / it's attached / it's assigned / it's active / it completed / it's generating / it's in Timeline / it's in Library / the scene contains…”:

1. Do I have verified **current** system state for this claim?
2. If no: query the owning subsystem before replying.
3. Sequence: **READ current state → COMPARE expected → CLAIM result**
4. Never: **REMEMBER previous claim → ASSUME it is true**

If state cannot be verified: `state unavailable / unverified`. Never invent scene IDs, asset IDs, completion, providers, jobs, references, assignments, saved assets, file presence, or generated outputs.

## Mutation law (standard Co-Director transaction)

```
USER REQUEST
→ RESOLVE INTENT
→ READ DESTINATION STATE
→ PERFORM TOOL ACTION
→ READ DESTINATION STATE AGAIN
→ VERIFY MUTATION
→ REPORT RESULT
```

Tool dispatch is not success. Tool response alone may not be enough. Where practical, success requires destination confirmation.

If the tool says success but destination does not match: **VERIFICATION FAILURE** — *The operation was attempted, but I could not verify the change in the destination system.* No fabricated completion.

## Ownership, cross-system, partial success

Each subsystem owns its truth. Co-Director queries the owner; it does not infer state from chat.

| Truth | Owner |
| --- | --- |
| Timeline / Timed Prompt | Timeline store |
| Character | Character store / global registry |
| Prop / Environment | Prop / Environment store |
| Library | Library store |
| References | Scene / reference store |
| Voice | Voice assignment store |
| Jobs / generation | Job / render store |
| Provider | Provider / config state |

Cross-system commands verify each owner separately. One success does not imply the other. Partial success is reported exactly. Never “Done.”

UI is a projection. Prefer persisted backend/store state. For critical workflows: store verification plus owner-visible UI confirmation. If cached Co-Director state conflicts with a fresh read: **fresh read wins**.
