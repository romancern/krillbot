# Krillion Puffer Party bot

## Description

An experimental Puffer Party assistant that opens a Playwright-controlled Firefox window, suggests answers, and can submit them automatically. It saves observed questions and answers locally to improve future suggestions. Join or host your game in the browser window it opens.

## Installation

Install Python 3.10+ and [uv](https://docs.astral.sh/uv/getting-started/installation/), then run:

```sh
uv sync
uv run playwright install firefox
```

Create a `.env` file with your OpenAI API key. Optionally set an API-compatible endpoint and model:

```sh
OPENAI_API_KEY=your-key-here
# OPENAI_BASE_URL=http://127.0.0.1:8317/v1
# KRILLION_MODEL=gpt-6-luna
```

Environment variables take precedence over `.env`. Model availability and API charges depend on your provider.

## Instructions

Choose one mode and join a game in the Firefox window:

```sh
uv run krillion --overlay
```

The overlay displays answer suggestions while you play and submit answers yourself. Use **Regenerate** for new suggestions or **Switch to bot mode** to enable automatic submissions. Close the overlay or press Ctrl+C to stop.

```sh
uv run krillion --bot
```

The bot requests suggestions and submits an answer on your turn. Press Ctrl+C to stop.

For either mode, add `--code ABCD` to join a specific room, `--new` to host a private room, or `--ranked` for ranked matchmaking. The `--code`, `--new`, and `--ranked` options are mutually exclusive. Add `--name NAME` to join with a display name. Run `uv run krillion live --help` for all options.
