---
title: Using Storyboard Studio
summary: Storyboard Studio lets you work out the visual structure of a shot before you spend a video generation. You assemble production frames from the library. The board is the plan, not the cut.
category: storyboard
slug: using-storyboard-studio
tags: [storyboard, planning, 16:9]
difficulty: start
updated: 2026-10-06
status: published
seoTitle: Using Storyboard Studio in Adept UI
seoDescription: Plan shots in Adept UI Storyboard Studio with library frames before you generate video. Boards support 16:9 and 9:16.
related: [aspect-ratios, storyboard-to-video, understanding-the-workflow]
---

## What this does

Storyboard Studio is the planning room. You lay out panels so you can see the shot before a video model spends time on it. The studio's own line for this room is simple: AI creates the art; Adept builds the board.

## Why you would use it

A wrong composition is expensive to discover after a five-second clip. A board lets you check who is in frame, how tight the shot is, and whether the next panel continues the idea.

## How to build a board

1. Open the project and Storyboard Studio.
2. Choose 16:9 or 9:16. Those are the storyboard aspects. Changing aspect keeps the panels linked to the same board.
3. Pull frames from the project library. Generate stills first if the library does not have the picture yet.
4. Arrange the panels in story order.
5. When a panel is the one you want to move, take it into video generation or the Timeline as a planned frame, not as if it were already a clip.

## What to expect

An empty board is a real state. It means you have not placed frames yet. It does not mean generation failed.

![Storyboard Studio](/product/adept-ui-ai-storyboard-studio.webp)

## Technical notes

Storyboard references are production assets. They can be passed downstream into generation workflows that accept them. A panel does not automatically become a Timeline shot until you place or generate that shot.

## Common mistakes

Using the board as a gallery of unrelated images. A storyboard is a sequence. If the panels do not follow one shot, the video step will not invent the sequence for you.
