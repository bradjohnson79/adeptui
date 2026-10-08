---
title: Projects, Scenes, and Assets
summary: A project holds the film. A scene holds an ordered stretch of shots. An asset is a still, clip, voice, or reference that belongs to that project.
category: getting-started
slug: projects-scenes-assets
tags: [project, scene, asset, library]
difficulty: start
updated: 2026-10-06
status: published
seoTitle: Projects, Scenes, and Assets in Adept UI
seoDescription: How Adept UI projects, scenes, and library assets fit together so a shot stays attached to the film.
related: [understanding-projects, glossary, what-is-timeline]
---

## What this does

These three words are the storage model. If you know which one you are editing, you know whether a change affects the whole film, one sequence, or one file.

## How they fit

- **Project.** The open production. Characters and the library live here.
- **Scene.** A sequence of shots on the Timeline. Extending a scene means adding or continuing shots, not creating a new project.
- **Asset.** A piece of media in the library: an image, a clip, a voice take, a reference sheet. Assets can be placed into a storyboard or a Timeline shot.

## Why the distinction matters

A retake replaces the generation you choose to run again. It does not delete the project. Deleting or losing an asset can break a shot that pointed at it. The scene is the edit. The asset is the media.

## What to expect

Approved and placed work is meant to survive a reload of the project. If a clip vanishes after you reopen, treat that as a problem with the save, not as a cue to generate a replacement in a different project.

## Technical notes

Reference sheets are assets with a production role. A character reference sheet, an environment reference sheet, and a prop reference sheet are different roles. The glossary defines the short names CRS, ERS, and PRS.
