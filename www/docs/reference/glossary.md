---
title: Glossary
summary: Short definitions for the words Adept UI uses in production: project, shot, reference sheets, continuation, retake, Co-Director, MAGI, and local versus hosted models.
category: reference
slug: glossary
tags: [glossary, terminology, crs, ers, prs]
difficulty: start
updated: 2026-10-06
status: published
seoTitle: Adept UI Glossary
seoDescription: Plain definitions for Adept UI terms including scene, shot, CRS, ERS, PRS, continuation, retake, Co-Director, and MAGI.
related: [projects-scenes-assets, character-identity-and-references, what-is-timeline]
---

## Production words

**Project.** The open film. Library, characters, and scenes belong to it.

**Scene.** An ordered stretch of shots on the Timeline.

**Shot.** One generation placed in a scene. It has references, a model, and a result.

**Asset.** A file in the project library: still, clip, voice, or reference.

**Character.** A saved identity: profile, look, references, and voice.

**Environment.** The place a shot happens. In the current studio that is an environment reference, not a SceneCraft scene.

**Prop.** An object with its own reference sheet.

**Library.** The project's media. New generations land here.

## Reference sheets

**Reference.** Media attached to a shot with a role. The role tells the model what the file is for.

**CRS.** Character reference sheet. Marked with `@` where reference tokens are used.

**ERS.** Environment reference sheet. Marked with `#`.

**PRS.** Prop reference sheet. Marked with `%`.

**Start frame.** The picture a shot should begin from, when the model supports it.

**End frame.** The picture a shot should arrive at, when the model supports it.

## Generation words

**Text-to-video.** A clip requested from a prompt, without a start still.

**Image-to-video.** A clip requested from a still you already have.

**Reference-to-video.** A clip conditioned by references such as a character or environment sheet, when the model accepts them.

**Continuation.** A new generation that carries a shot forward, often from its last frame. It does not promise an exact match.

**Retake.** A new generation of a shot you chose to run again.

**Local model.** A model that runs on your machine after it is installed.

**API model.** A hosted model. The request goes to a connected provider. Hosted video uses fal.ai.

## Product names

**Co-Director.** Project-scoped help across the open film. It does not silently change the project.

**MAGI.** Finishing: grade, upscale when a GPU path is available, overlays, and export.

**SceneCraft.** Spatial reconstruction planned for a later release. Not a current production room.

**Adept Setup.** The readiness room: Guided, AI-Guided, and Manual.
