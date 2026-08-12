# Install Plan

## Plan contract

`InstallPlan` summarizes a creator-reviewable action before any trusted install begins.

Fields include:

- component id/name
- action (`install`, `update`, `repair`, `link_existing`)
- runtime confirmation requirement
- model download confirmation requirement
- current version
- target certified version
- recommended source
- ordered steps
- warnings/notes

## Confirmation rules

- Runtime changes always require explicit approval.
- Large model downloads require a second explicit confirmation.
- Plans must explain that Source Manager performs the install.

## Current execution

The UI still routes actual install execution through existing setup/install-job flows, preserving progress, retries, repair, and verification behavior.
