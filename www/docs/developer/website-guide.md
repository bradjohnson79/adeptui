---
title: Website Guide
summary: The public website has one guide dock. It answers from published documentation through a rebuildable index. It is not Co-Director, and it does not change the studio.
category: developer
slug: website-guide
tags: [website, documentation, guide]
difficulty: technical
updated: 2026-10-06
status: published
seoTitle: Adept UI Website Guide
seoDescription: How the public Adept UI website guide retrieves documentation, cites sources, and calls its conversation model.
related: [architecture-overview, contributing]
---

## What this does

The website guide is a chat dock on the public site. It helps a visitor find a documented answer about Adept UI. It is a separate system from Co-Director. Co-Director lives inside the studio. This guide only reads public website knowledge and explains it.

## How indexing works

Published Markdown in the website docs is the source of truth. When the website server starts, it reads those articles, skips anything that is not published, and splits each article around its headings. Each piece keeps its title, category, article, slug, heading, URL, tags, updated date, and source type.

The same pass adds a few public website facts: the download note, the model names already published on this site, the GitHub repository, and the statement that an official Hugging Face destination is not available. FAQ lines from the homepage are included too.

There is no separate vector database. The index stays in memory and is rebuilt from the files. Changing an article and restarting the website server is how the guide learns the new text. You do not rewrite the guide prompt for each article.

## How retrieval works

A question is searched two ways. Keyword search catches exact technical strings. A local vector catches nearby wording, such as asking about video size when the article says resolution or aspect. The two scores are combined. The guide sends only the few closest passages, not the whole library.

If the question names an error code that never appears in the published pages, nothing is retrieved for that code. The guide should say the documentation does not establish it.

The page the visitor is reading is sent as a URL, title, category, and article slug. A question like “why would I use this?” prefers that article. The browser does not send an address, a history, or an account.

## How the model is configured

Conversation uses GPT-5 mini. The API identifier is `gpt-5-mini`. It is set in one server file. If `CHAT_MODEL` is set to anything else, the server refuses the call instead of substituting a different model.

The key stays in `OPENAI_API_KEY` on the server. Do not put it in a `VITE_` variable. The browser only posts the question, a short session of recent turns, and the page context to `/api/guide`. Answers stream back as simple HTML: paragraphs, lists, emphasis, and links. The browser keeps only those tags. Sources are the pages the retriever actually selected, usually one to three.

Copy `.env.example` to `.env` for a local run. Never commit `.env`.

## How to run it locally

From the website project, start the preview or dev server. The guide route is part of that server. Without a key, the dock still opens and tells the visitor the guide is temporarily unavailable, and that documentation search still works.

The public endpoint limits how often one visitor can ask, rejects oversized questions, and refuses requests for prompts, keys, or files outside the published knowledge. It does not install software, edit a project, or run commands. The limit uses the connection address. A reverse proxy may pass the visitor address only when `GUIDE_TRUST_PROXY=1`.

## Adding a knowledge source

Add a published article, or extend the small set of verified public facts next to the docs reader. A future source has to be chosen on purpose: GitHub files, Hugging Face, release notes, or model cards. The guide does not browse the open web.

Restart the website server after the change so the index rebuilds.
