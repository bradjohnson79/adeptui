---
title: Local Services
summary: Developer reference for the local services behind Adept UI. Creators do not configure these ports. The film is opened in the desktop studio.
category: reference
slug: local-services
tags: [ports, studio api, developer]
difficulty: technical
updated: 2026-10-06
status: published
seoTitle: Adept UI Local Services and Ports
seoDescription: Developer reference for Adept UI local services. These ports are not creator settings.
related: [architecture-overview, comfyui-and-the-local-runtime, generation-failed-or-stuck]
---

## Who this is for

This page is for someone debugging the studio on a machine they maintain. A filmmaker should not open these addresses to make a shot. Adept UI is supposed to start and recover its own local services.

## Services

| Service | Port | What it is |
| --- | --- | --- |
| Studio API | 8758 | The local service the studio interface calls |
| Local creator UI | 5173 | The local studio interface when it is served for development |
| Local generation runtime | 8188 | The ComfyUI runtime Adept UI uses for local models |

The public marketing site is not one of these services. Do not treat a website preview as the studio.

## Retired address

Port 8760 is not the product interface. Older notes that send you there are stale.

## How to use this list

If a developer tool cannot reach the studio service, the port tells you what failed to answer. It does not tell you to kill a process. The generation runtime in particular is protected infrastructure. An unexpected stop is an incident, not a cache clear.

## What this page does not include

No tokens, no command lines that start or stop services, and no extra model ports. If a service is missing from this table, it is not part of the public reference.
