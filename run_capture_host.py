#!/usr/bin/env python
"""Thin repo-root shim so `python run_capture_host.py` works directly.

Equivalent to (and prefer, per the restructuring to a uv-managed project):
    uv run pulse-capture-host
    uv run python -m pulse_capture.desktop.run

This shim only works if pulse_capture is importable on sys.path -- true
inside the uv-managed venv (`uv run python run_capture_host.py`), or after
`uv sync` + activating .venv yourself.

See pulse_capture/desktop/run.py for the operational requirements
(foreground-only, Ctrl+C to stop, never installs as a service/scheduled
task/startup entry).
"""

from pulse_capture.desktop.run import main

if __name__ == "__main__":
    raise SystemExit(main())
