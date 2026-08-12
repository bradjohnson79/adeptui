# M42 W47 — Security Model (Law 27)

## Hard denies (default)

- Privileged containers
- Host network mode
- Docker socket mounts (`/var/run/docker.sock`, `\\.\pipe\docker_engine`)
- Broad host-drive writable mounts
- Credential directory mounts
- Unrestricted environment inheritance of API keys
- Unpinned `:latest` images for user-added installs (warning → block unless advanced policy)

## Allowed

- Isolated private volumes
- Read-only shared-optional model mounts
- Job-scoped input (RO) / output (RW) mounts
- Explicit GPU device requests via NVIDIA Container Toolkit

## Uninstall safety

Never silently delete: project assets, generated media, Timeline lineage, Bible records, provenance, shared models/LoRAs/nodes, credentials.

## Core protection

`core_mandatory` runtimes never expose standard Uninstall. Repair Installation only.
