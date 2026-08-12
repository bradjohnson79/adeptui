# Certification Thresholds

| Status | Rule |
| --- | --- |
| `not_tested` | No evidence for scope |
| `benchmarking` | Run in progress |
| `insufficient_evidence` | Samples < 3 |
| `experimental` | Human reviewed, not promoted |
| `certified_subtle` | Promoted bilingual-subtle |
| `certified_balanced` | Promoted bilingual-balanced |
| `certified_strong` | Promoted bilingual-strong |
| `english_preferred` | Refined English wins |
| `no_material_difference` | Strategies statistically tied |
| `bilingual_not_recommended` | Bilingual loses vs English |
| `regressed` | New revision worse than prior |
| `disabled` | Manually disabled |

Scope key: `providerId + modelRevision + domain + category + strategy`.

Stale: modelRevision or workflowRevision change → `not_tested`.
