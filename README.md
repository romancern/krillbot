# Krillion Puffer Party bot

The experimental live bot opens a separate Playwright-controlled Firefox window. Join or host a game in that window. It logs visible questions and whose turn it is, asks OpenAI for candidates, and submits a candidate when the game indicates it is your turn. It opens a separate browser session and cannot attach to an existing browser tab.

## Setup

Python 3.10+ is required. From this folder:

```sh
uv sync
uv run playwright install firefox
```

Configure your API key, endpoint, and model in the ignored `.env` file. For the local CLIProxyAPI service:

```sh
OPENAI_API_KEY=your-key-here
OPENAI_BASE_URL=http://127.0.0.1:8317/v1
KRILLION_MODEL=gpt-6-luna
```

Run `uv run krillion --bot` after saving `.env`. Environment variables take precedence over `.env`. Choose **Quick Play** or join your friends' room in the Firefox window that opens. The bot starts automatically once it sees a category and your turn. Stop it with Ctrl+C. For a specific room, use `--code ABCD`. Set `KRILLION_MODEL` or pass `--model MODEL` to override the default `gpt-6-luna`. API calls incur charges. The bot requests candidates as soon as it sees a question to reduce delay; the terminal logs model latency. Availability, cost, and actual latency depend on your API account and have not been tested here.

To join ranked matchmaking automatically, run:

```sh
uv run krillion --bot --ranked --name Krillbot
```

Ranked uses a separate persistent Firefox profile at `~/.krillion-bot/firefox-ranked` so the browser-stored rating can persist. It defaults to a 4–6 player table; select another size with `--table-size 1v1`, `3s`, `4-6`, or `8-10`. Ranked games affect the rating. `--ranked` and `--code` cannot be used together.

To host a new private room and print its invite code, use `uv run krillion -o --new --name ph4ntom` (or use `-b` for bot mode). Start the game in the browser when your friends have joined. `--new`, `--code`, and `--ranked` are mutually exclusive.

To watch without an API key or submissions, use `uv run krillion --bot --observe --code ABCD`. You can join manually in the window, or add `--name Krillbot` to request a seat.

Choose exactly one mode for every live run: `--bot` (`-b`) or `--overlay` (`-o`).

## Show hints on screen

Run `uv run krillion --overlay` to open a floating hints window alongside the game browser. Join a game in that browser. The window shows the question, whose turn it is, and up to eight ordinary and two specific suggestions; type and submit your own answer in the game. Used answers disappear when detected. Press **Regenerate** for a fresh set. **Switch to bot mode** lets the bot submit answers on your turns; switch back to hints mode at any time. Close the hints window or press Ctrl+C to stop. Combine `--overlay` with `--code ABCD --name Krillbot` or `--ranked` as needed.

## Current limitations

- The prompt, turn status, input, and rejection CSS selectors were found in the current site client. The bot detected a real question and two player turns in a live room; the input and turn indicators were also observed in the normal Firefox window. The full automated path has **not** yet been verified in a live round with an API key. Site updates may break selectors.
- Visible successful answer bubbles are used to exclude already played answers; an own successful bubble is recorded as accepted, along with its tier when visible. A visible `no echo` rejection is recorded as rejected. A repeat warning is not treated as evidence that an answer is invalid. If the turn changes without explicit recognizable feedback, the bot logs the result as **unknown**, not accepted. Bubble capture is best effort and has not yet been verified in a live automated game.
- The bot tracks its own attempts and visible successful answer bubbles within a category, but may miss bubbles when joining mid-round or during rapid changes. It may receive a repeat rejection. Generation can miss a short turn, and when no candidate is available the bot waits rather than inventing a result.
- A Playwright Firefox session is separate from your usual Firefox session; join in the window the command opens. Stopping the command closes that window.

## Local evidence

The database is `krillion.sqlite3` by default; pass `--db PATH` before the subcommand to change it. Question and mode matching are exact. Previously accepted answers are preferred, with recognized observed Puffer Party tiers ranked from rarest to most common. The model is asked for rare valid candidates when needed. Generated candidates are saved as `suggested`, never as accepted. Only explicitly observed results should be recorded with scores or rarity; no player names are required.

```sh
uv run krillion record 'Name a type of skincare product' 'moisturizer' --status accepted --source 'observed in Puffer Party'
uv run krillion suggest 'Name a type of skincare product' --used moisturizer
uv run python -m unittest discover -s tests
```
