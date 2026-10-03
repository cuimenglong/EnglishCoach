# English Coach

An LLM-powered English expression improvement tool built with [Textual](https://textual.textualize.io/) TUI.

It talks to you through an LLM to assess your level, creates a personalized course plan, then coaches you day by day with exercises, corrections, and a vocabulary bank.

## Features

- **Level assessment** — The LLM has a conversation with you to understand your English level, strengths, weaknesses, and goals.
- **Personalized course plan** — A structured multi-day plan is generated based on your profile, with varied exercise types: free writing, gap fill, error finding, sentence rewriting, translation challenge, paragraph writing, role play, opinion expression, summary writing, and more.
- **Daily coaching** — Each day the coach interacts with you around the plan's topic, gives gentle corrections, and weaves in micro-exercises.
- **Daily summary** — Type `/summary` to end a session. The LLM generates a structured summary with mistakes, corrections, new expressions, and suggestions.
- **Vocabulary bank** — Save useful expressions during training. The LLM can also save them for you automatically.
- **Progress tracking** — Day advances only when you complete a session (`/summary`). Resume anytime.
- **Dynamic student profile** — After every `/summary`, the LLM updates an evolving profile (CEFR level, skill scores, strengths/weaknesses, interests, difficulty, pace) that the coach uses to personalize the next session.
- **Terminal UI** — Runs in the terminal with a clean, dark-themed TUI. All text is in English.
- **Portable** — Single-file exe (self-contained, no dependencies to install).

## Quick Start

### Option A: Run the pre-built exe
1. Go to `dist/` and double-click `EnglishCoach.exe`.
2. First launch: configure your API key in the Settings screen.
3. Start the assessment conversation.
4. Complete the assessment, and a course plan will be generated automatically.
5. Begin Day 1 training.

### Option B: Run from source
```bash
# Clone or cd into the project
cd EnglishCoach

# Install dependencies
pip install -r requirements.txt

# Run
python run.py
```

### First-time configuration

When you launch the app with an empty API key, you will be taken to the Settings screen automatically. Fill in:

- **API Key** — Your OpenAI-compatible API key
- **Model Name** — e.g. `gpt-4o`, `deepseek-v4-flash`, etc.
- **Base URL** — API endpoint (defaults to `https://api.openai.com/v1`)
- **Temperature** — LLM creativity (0.0 - 2.0, default 0.7)

Press **Save & Continue** to proceed.

## Usage

### Available commands (type in the chat input)

| Command | Action |
|---|---|
| `/summary` | End today's session and generate a daily summary. Advances to the next day. |
| `/practice` | Request an exercise related to today's focus. |
| `/save` | Save an expression to your vocabulary bank (type it after the prompt). |
| `/explain` | Ask for a grammar or usage explanation. |
| `/plan` | View the full course plan. |
| `/vocab` | Browse your vocabulary bank. |
| `/help` | Show available commands. |

### Daily flow

1. Open the app — you'll see today's topic and focus in the sidebar.
2. Chat with the coach naturally. Write in English.
3. The coach will correct mistakes and offer micro-exercises.
4. When you're done, type `/summary`.
5. The LLM generates a structured summary and saves it.
6. Close the app. Next time you open it, it jumps to the next day.

### Keyboard shortcuts

- `Ctrl+C` — Quit the app
- `Tab` / `Shift+Tab` — Navigate between widgets
- `Escape` — Go back / close a screen

## Project structure

```
EnglishCoach/
├── run.py                  # Entry point
├── src/
│   ├── app.py              # Main Textual app and navigation
│   ├── config.py           # Config loading/saving (settings.json)
│   ├── course_plan.py      # Course plan generation (LLM)
│   ├── daily_coach.py      # Daily coach system prompt builder
│   ├── knowledge.py        # Vocabulary bank (SQLite + FTS5)
│   ├── llm_client.py       # OpenAI-compatible API client
│   ├── profile.py          # User profile model
│   ├── dynamic_profile.py  # Evolving student profile (scores, weaknesses, pace)
│   ├── sessions.py         # Session management and progress
│   ├── summary.py          # Daily summary generation
│   ├── utils.py            # File I/O and path helpers
│   └── tui/
│       ├── screens/        # Settings, Assessment, Coach, History, etc.
│       └── widgets/        # Chat message formatters
├── requirements.txt
└── EnglishCoach.bat        # Launcher for the exe
```

## Building the exe yourself

```bash
pip install pyinstaller
pyinstaller run.py --onefile --name EnglishCoach --icon icon.ico --add-data "src;src"
```

The output will be in `dist/EnglishCoach.exe`.

## Development

```bash
pip install -r requirements-dev.txt

# Run the test suite
python -m pytest tests/ -q

# Headless smoke test: mounts every screen
python tests/smoke_app.py
```

### Logs

Errors are written to `data/englishcoach.log` (not stdout, so they never
corrupt the TUI). If a session behaves oddly — for example the course plan
falls back to a generic version because the LLM call failed — check this file
first.

## Data storage

All user data is stored in a `data/` directory beside the exe (or the project root when running from source):

- `knowledge.db` — Vocabulary bank
- `user_profile.json` — Assessment results and last completed day
- `dynamic_profile.json` — Evolving student profile (CEFR level, skill scores, strengths, pace)
- `course_plan.json` — Your course plan
- `session.json` — Current session state
- `daily_logs/` — Daily summaries (Markdown)

To migrate, copy the whole `data/` folder along with the exe.

## Requirements

- Python 3.11+
- An API key for an OpenAI-compatible LLM service

## License

MIT
