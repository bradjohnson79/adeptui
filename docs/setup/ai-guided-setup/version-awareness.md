# Version Awareness

## Rule

Updates are offered only when a newer Adept-certified recipe exists.

## Inputs

- live component verification version/revision
- persisted certification record version
- certified recipe registry version/date

## Forbidden behavior

- no auto-chasing arbitrary upstream latest
- no silent provider switch
- no silent re-certification after a changed runtime

## Current implementation

`check_updates()` compares the persisted certification record to the latest recipe for that component and only reports `Update Available` when the certified registry changed.
