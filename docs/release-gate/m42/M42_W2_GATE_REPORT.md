# M42 Wave 2 — Gate Report

See `artifacts/m42/w2/wave2_gate_results.json` for the machine-readable evaluation.

## GO conjunction

```text
prerequisitesPreserved
∧ requiredLocalLeafCertificationPassed
∧ requiredLocalProductionPathCertificationPassed
∧ requiredLocal ⊆ certifiedProductionPathWorkflowKeys
∧ resolverProductionModePassed
∧ queueWorkerExecuteOnly
∧ outputGateOperational
∧ provenanceOperational
∧ certificationLedgerImmutable
∧ fingerprintValidationPassed
∧ consumerContractPassed
∧ cancellationPassed
∧ retryWithoutDuplicatePassed
∧ noBuilderBypass
∧ noResolverBypass
∧ noQueueWorkerBypass
∧ noOutputGateBypass
∧ noAssetRegistrationBypass
∧ noFakeCompletion
∧ ModernModelFoundationReady
→ wave2Go
```

Required local keys (stable):

- `zimage.txt2img`
- `zimage.ref_edit`
