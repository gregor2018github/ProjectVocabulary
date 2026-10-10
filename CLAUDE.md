# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Taalbrug** (Dutch for "language bridge"; constants `APP_NAME` / `APP_TAGLINE`) is a Dutch-German vocabulary trainer desktop app built with PyQt6. Users train vocabulary via a slider-based scoring system, with AI-powered sentence generation and text-to-speech via the OpenAI API.

## Running the App

```bash
# Activate the virtual environment
source vocab_envi/Scripts/activate   # Windows Git Bash
# or: vocab_envi\Scripts\activate    # Windows CMD

# Run
python app_main.py
```

Requires the `OPENAI_API_KEY` environment variable to be set (checked at startup).

## Architecture

Everything lives in a single file: `app_main.py`. There are no tests. The app uses three global instances (`gui`, `logic`, `aiapi`) initialized in `main()`.

### Key Classes

- **`Data`** — Static class managing vocabulary state. Loads/saves from `files/vocabulary_data.json` (stats) and `files/VOCABS.xlsx` (word list). All fields are class-level lists (not instance attributes).
- **`GUI`** — PyQt6 interface. Handles all screens: main menu, training, statistics, AI training, settings. Uses `pygame.mixer` for audio playback.
- **`Logic`** — Training logic: word selection (weighted by correctness, frequency, recency), scoring, mode tracking (`DG`=Dutch-German, `GD`=German-Dutch, `RA`=random, `AI`=AI mode).
- **`AiApi`** — OpenAI API wrapper for sentence generation (`gpt-4o-mini`) and text-to-speech (`tts-1`).
- **`Table`** — `QAbstractTableModel` subclass for the statistics table view.
- **`BarChart`** — QPainter column chart (no charting dependency) used by the Activity tab of the statistics screen.
- **`SplashOverlay`** — animated brand intro painted over the main window at startup (~4.3 s + fade, click/key skips), then fades out to reveal the main menu.

### Data Flow

1. Startup: `Logic.search_vocabulary_data()` tries JSON first, falls back to XLSX, or creates an example XLSX if neither exists.
2. XLSX can be expanded by appending rows; `refresh_vocabulary_list()` merges new XLSX entries into existing JSON stats.
3. Statistics are persisted to JSON after each training answer.
4. Usage is recorded in the `activity_log` SQLite table via `Data.log_activity()` (events: `app_start`, `trained`, `added`, `deleted`). There is no backfill — data from before tracking existed is deliberately ignored. `Logic.create_activity_data()` aggregates it for the charts.

## Config

`config.py` holds path constants: `XLSX_FILE`, `JSON_FILE`, `MAIN_PATH`, `FILES_PATH`.

## Dependencies

Key packages (installed in `vocab_envi` venv): `PyQt6`, `openai`, `pandas`, `openpyxl`, `pygame`, `numpy`.

## Known Patterns / Gotchas

- The codebase uses `os.chdir()` to switch directories for file I/O — be careful with relative paths.
- Languages are currently hardcoded to Dutch and German throughout.
- AI training mode only works for Dutch->German direction currently.
- The `Data` class uses class-level mutable lists shared across all usage — there are no instances.
- Colors live in the `THEMES` palettes (light/dark). `GUI.STYLESHEET` uses `$token` placeholders filled by `GUI.apply_theme()`, and painted widgets read the active `THEME` dict — don't hardcode hex colors in new UI. The chosen theme is stored in the SQLite `settings` table.
