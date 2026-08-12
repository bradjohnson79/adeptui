# Monitoring

## Goal

Catch drift after a component was installed or certified, especially:

- missing files
- stale or failed install jobs
- verification regressions
- runtime restart-required posture

## Current behavior

- lifecycle monitor findings are derived from live verification plus install-job state
- certified components with drift downgrade to `Repair Recommended` or `Repair Required`
- monitor results surface in the AI-Guided panel and component lifecycle metadata

## Scope

This monitor is lightweight and synchronous. It runs as part of setup status/lifecycle reads rather than as a separate daemon.
