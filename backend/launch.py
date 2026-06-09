"""One-command launcher for BUD.

Starts the FastAPI app (which serves both the API under ``/api/*`` and the
compiled React SPA) with uvicorn on ``127.0.0.1`` and opens the user's browser
to the app once the server is up.

Usage::

    uv run bud
    uv run python -m backend.launch

Environment variables:

- ``BUD_HOST``: interface to bind to (default ``127.0.0.1``, loopback only).
  Set ``BUD_HOST=0.0.0.0`` to bind all interfaces and expose the app on the
  LAN. WARNING: BUD has no authentication; only do this on a trusted network
  or behind a reverse proxy.
- ``BUD_PORT``: port to listen on (default ``8000``).
- ``BUD_NO_BROWSER=1``: do not open a browser (useful for servers/tests).
"""

import os
import threading
import webbrowser

import uvicorn

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def _host() -> str:
    return os.environ.get("BUD_HOST", DEFAULT_HOST) or DEFAULT_HOST


def _port() -> int:
    try:
        return int(os.environ.get("BUD_PORT", DEFAULT_PORT))
    except ValueError:
        return DEFAULT_PORT


def _browsable_host(host: str) -> str:
    """Return a host usable in a browser URL.

    ``0.0.0.0`` (and the IPv6 equivalent ``::``) are bind-all addresses, not
    routable destinations, so substitute loopback when opening/printing a URL.
    """
    if host in ("0.0.0.0", "::", ""):
        return "127.0.0.1"
    return host


def _open_browser(url: str) -> None:
    try:
        webbrowser.open(url)
    except Exception:
        # Never let a browser-launch failure take down the server.
        pass


def main() -> None:
    host = _host()
    port = _port()
    url = f"http://{_browsable_host(host)}:{port}"

    print(f"BUD running at {url} (Ctrl+C to stop)")

    if os.environ.get("BUD_NO_BROWSER") != "1":
        # uvicorn.run blocks, so schedule the browser open slightly after the
        # server has had time to come up.
        threading.Timer(1.2, _open_browser, args=(url,)).start()

    uvicorn.run("backend.main:app", host=host, port=port)


if __name__ == "__main__":
    main()
