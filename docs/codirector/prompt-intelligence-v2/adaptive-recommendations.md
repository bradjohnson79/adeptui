# Adaptive Recommendations

## Resolve order

1. Manual override
2. Project `strategyMode`
3. Category evidence
4. Profile default
5. `refined-english`

## strategyMode

| Mode | Behavior |
| --- | --- |
| `manual` | Never auto-apply strategy |
| `recommend` | Surface recommendation; user Preview/Apply |
| `automatic_certified` | Apply only exact certified evidence for provider/modelRevision/domain/category |

Never auto-apply experimental / not_tested / insufficient_evidence.

Final prompt always previewable. Applied strategy persisted on generation metadata.
