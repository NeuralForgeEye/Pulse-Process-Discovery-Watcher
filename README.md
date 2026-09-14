# Pulse-Process-Discovery-Watcher

R&amp;D and architecture workspace for Pulse: a metadata-based process discovery tool that mines real QA/QC workflows across multiple applications without OCR or video, using structured event capture and cross-application identifier linking.

See `plans/pulse-architecture.md` for the full design and `plans/BUILD-STATUS.md` for what is actually built vs. still blueprint-only.

---

## Setup

This project uses [`uv`](https://github.com/astral-sh/uv) to manage the Python environment and dependencies.

```
uv sync
```

If `uv` isn't available in your environment, plain-pip fallbacks are exported:

```
pip install -r requirements.txt          # runtime deps only
pip install -r requirements-dev.txt       # + dev tools (pytest, ruff, mypy)
pip install -r requirements-lock.txt      # fully pinned, for reproducible installs
```

---

## Running the capture host

**Operational requirements (by design, not optional):**
- Runs only as a manually-started foreground process — one command starts it, nothing launches it automatically.
- It is **never** registered as a Windows service, scheduled task, or startup entry, and never will be without a separate explicit request.
- While running, it prints a continuously-updating status line so it's always obvious it's active.
- **Ctrl+C** stops it cleanly: it flushes every pending event to the database before exiting — never a bare kill.

Start it:

```
uv run pulse-capture-host
```

(equivalently: `python run_capture_host.py`, or `python -m pulse_capture.desktop.run` from inside `uv run`)

Optional flags:

```
uv run pulse-capture-host --db pulse.db --state-dir .pulse_state --idle-threshold-s 60
```

| Flag | Default | Meaning |
|---|---|---|
| `--db` | `pulse.db` | Path to the SQLite event store |
| `--state-dir` | `.pulse_state` | Local directory holding the actor-id salt file |
| `--idle-threshold-s` | `60` | Seconds of no input before an `idle_start` event fires |

Press **Ctrl+C** to stop. You'll see:
```
Shutting down - flushing pending events...
Stopped cleanly.
  raw events seen:  ...
  events written:   ...
  ...
```

---

## Viewing what was captured

`pulse.db` is a binary SQLite file — opening it directly in a text editor shows raw bytes, not readable data. Use the built-in viewer instead:

```
uv run python view_events.py --last 30
```

Prints a plain, time-ordered table: time, app, window, action. Useful flags:

```
uv run python view_events.py --db pulse.db --last 100          # more history
uv run python view_events.py --type click,window_opened         # filter to specific event types
uv run python view_events.py --all                              # include noisy focus_changed events (collapsed by default)
```

---

## Running the test suite

```
uv run pytest tests/ -m "not slow"     # fast tests only (~1 min)
uv run pytest tests/ -m ""              # full suite, including slow/timing-sensitive tests (several minutes)
```

Notes:
- Some tests drive real fixture apps and synthetic mouse/keyboard input (`SendInput`) against a real, unlocked, interactive Windows desktop session — **avoid touching your mouse/keyboard while these run**, since they share the one system cursor with you.
- Tests marked `windows_only` require a real Windows desktop session (hooks, HWNDs, a message pump) — they won't run meaningfully in a headless/CI environment without one.
- Tests marked `slow` exercise real timing (crash-safety kill tests, throughput, latency measurement) and take noticeably longer.

---

## Linting and type-checking

```
uv run ruff check src tests
uv run mypy src
```
