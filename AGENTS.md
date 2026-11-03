# Krillion Puffer Party bot

## Goal

Build a bot for Krillion (https://krillion.io/) Puffer Party that suggests and eventually submits strong answers, while learning from results and answers shown by other players. The user intends to play with friends.

## Intended behavior

- Read the current question and look for a matching question in a persistent local dataset.
- Prefer a previously accepted, high-scoring answer when the question and its constraints match. Otherwise, use a fast language model, with GPT-6 Luna as the preferred candidate, to suggest 10 answers: 8 ordinary and 2 special. Treat the special answers as especially unusual, potentially high-scoring candidates; all suggestions remain unverified until observed in the game.
- Submit or present an answer as appropriate to the implementation stage. Record the actual outcome when visible.
- Capture answers shown from other players when available. Distinguish observed answers from accepted answers, rejected answers, untested model suggestions, and inferred information. Store scores or rarity only when observed, with provenance.
- Keep the exact question text and qualifiers, answer spelling, source, timestamps, game mode, and observed result. Avoid assuming that a score or acceptance transfers between differently worded questions or modes.
- Retain multiple answers per question and improve selection as evidence accumulates. Avoid recording unnecessary player identity information.

## Technology

- Implement the entire bot in Python. Use Playwright for Python to interact with the site and read page elements.
- The user observed a prompt rendered as a page element, for example `<div class="prompt">Name a type of skincare product</div>`. Use the DOM to read prompts; verify the selector and its behavior in Puffer Party before relying on it.

## What is not yet established

- Puffer Party's UI, timing, rules, scoring, answer visibility, and whether it shares questions or answer tiers with other modes need to be observed and verified.
- The community dataset at https://github.com/StruggleYang/krillion-dataset covers historical Daily Dive questions and sampled tiered answers; it is not known to cover Puffer Party. Its records may contain inconsistencies. Treat it as an optional, attributed source, not ground truth for multiplayer.
- Model availability, latency, cost, and integration details must be checked in the actual environment. Do not assume Luna meets the round deadline without measuring it.

## Starting approach

1. Inspect the actual game flow and what information is visible before choosing an automation method. Ask the user for access or a live session if needed; do not assume access to their account or friends' games.
2. Choose a simple local stack and persistent storage suited to the observed flow. Separate screen/input integration, question matching, answer generation, storage, and selection so each can be tested independently.
3. Build an initial manual or assisted flow that accepts a question, searches stored observations, requests candidates from the model when needed, and records results. Then integrate game interaction and capture of other players' visible answers as supported by the UI.
4. Measure question match rate, answer acceptance, scores when available, and end-to-end latency. Test matching with qualifiers and ensure unverified suggestions are never mislabeled as accepted.

Keep configuration and API keys outside source control. Make sensible implementation choices and document setup and known limitations as the project takes shape.
