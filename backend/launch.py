"""One-command launcher for BUD.

Starts the FastAPI app (which serves both the API under ``/api/*`` and the
compiled React SPA) with uvicorn on ``127.0.0.1`` and opens the user's browser
to the app once the server is up.

Usage::

    uv run bud
    uv run python -m backend.launch

Environment variables:

- ``BUD_PORT``: port to listen on (default ``8000``).
- ``BUD_NO_BROWSER=1``: do not open a browser (useful for servers/tests).
"""

import os
import threading
import webbrowser

import uvicorn

HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def _port() -> int:
    try:
        return int(os.environ.get("BUD_PORT", DEFAULT_PORT))
    except ValueError:
        return DEFAULT_PORT


def _open_browser(url: str) -> None:
    try:
        webbrowser.open(url)
    except Exception:
        # Never let a browser-launch failure take down the server.
        pass


def main() -> None:
    port = _port()
    url = f"http://{HOST}:{port}"

    print(f"BUD running at {url} (Ctrl+C to stop)")

    if os.environ.get("BUD_NO_BROWSER") != "1":
        # uvicorn.run blocks, so schedule the browser open slightly after the
        # server has had time to come up.
        threading.Timer(1.2, _open_browser, args=(url,)).start()

    uvicorn.run("backend.main:app", host=HOST, port=port)


if __name__ == "__main__":
    main()
