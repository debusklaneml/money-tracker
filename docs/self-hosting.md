# Self-Hosting BUD (home server + iPhone LAN access)

A reproducible runbook for running BUD persistently on a home/mini server (Linux
or macOS) and reaching it from an iPhone on the same network.

> **Read first:** [Access control](./access-control.md). BUD has **no
> authentication** and serves your full financial history. Do not expose it on a
> network without the documented posture (loopback + reverse proxy with auth/TLS).

## Overview

BUD is a single Python process that serves both the JSON API and the compiled
SPA on one port. All data is one SQLite file (`~/.bud/cache.db`). Self-hosting is
therefore: build the SPA once, run the process headless, keep it alive across
reboots, put a reverse proxy in front for auth/TLS, and back up the one file.

## 1. Build and install on the server

```bash
git clone <your-fork-or-copy> bud && cd bud

# Frontend build (only when the frontend changes)
cd frontend && npm install && npm run build && cd ..

# Python deps + editable install
uv sync
```

## 2. Run headless

Run on loopback (the safe default) and front it with a reverse proxy (step 4).
`BUD_NO_BROWSER=1` stops it trying to open a browser on a headless box.

```bash
BUD_NO_BROWSER=1 BUD_PORT=8000 uv run bud      # binds 127.0.0.1:8000
```

Environment variables (see also the README):

| Var | Default | Purpose |
| --- | --- | --- |
| `BUD_HOST` | `127.0.0.1` | Interface to bind. `0.0.0.0` = all interfaces (LAN). Keep loopback and use a proxy — see access-control. |
| `BUD_PORT` | `8000` | Port to listen on. |
| `BUD_NO_BROWSER` | unset | Set to `1` to never open a browser (required headless). |
| `BUD_DB_PATH` | `~/.bud/cache.db` | Override the SQLite database location (e.g. point at a backed-up volume). |

> **Quick-and-dirty trusted-LAN option (no proxy):** `BUD_HOST=0.0.0.0
> BUD_NO_BROWSER=1 uv run bud`, then open `http://<host-lan-ip>:8000` on the
> phone. This sends your finances **unencrypted and unauthenticated** over the
> LAN — only acceptable on a network you fully trust, and never with
> port-forwarding. The proxy setup below is strongly preferred.

## 3. Keep it alive across reboots

### Linux — systemd (user service)

`~/.config/systemd/user/bud.service`:

```ini
[Unit]
Description=BUD budgeting app
After=network.target

[Service]
Type=simple
WorkingDirectory=%h/bud
Environment=BUD_NO_BROWSER=1
Environment=BUD_HOST=127.0.0.1
Environment=BUD_PORT=8000
ExecStart=%h/.local/bin/uv run bud
Restart=on-failure

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now bud.service
loginctl enable-linger "$USER"     # keep the user service running after logout
systemctl --user status bud.service
journalctl --user -u bud.service -f
```

(Adjust the `uv` path — `which uv`. For a system-wide service, drop it in
`/etc/systemd/system/` with an explicit `User=`.)

### macOS — launchd (LaunchAgent)

`~/Library/LaunchAgents/com.bud.app.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.bud.app</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/uv</string><string>run</string><string>bud</string>
    </array>
    <key>WorkingDirectory</key><string>/Users/YOU/bud</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>BUD_NO_BROWSER</key><string>1</string>
        <key>BUD_HOST</key><string>127.0.0.1</string>
        <key>BUD_PORT</key><string>8000</string>
    </dict>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>StandardOutPath</key><string>/tmp/bud.out.log</string>
    <key>StandardErrorPath</key><string>/tmp/bud.err.log</string>
</dict>
</plist>
```

```bash
launchctl load -w ~/Library/LaunchAgents/com.bud.app.plist
launchctl list | grep com.bud.app
```

(`which uv` to confirm the path; Apple-silicon Homebrew is `/opt/homebrew/bin/uv`,
Intel is `/usr/local/bin/uv`.)

## 4. Put a reverse proxy in front (auth + HTTPS)

Follow [access-control.md](./access-control.md) — the recommended setup is Caddy
listening on `:8443` with `basic_auth` + `tls internal`, reverse-proxying to
`127.0.0.1:8000`. Run it as its own service (systemd unit / `caddy start` / brew
service) so it survives reboots alongside BUD.

## 5. Reach it from your iPhone

1. Find the server's LAN IP:
   - Linux: `ip addr show` or `hostname -I`
   - macOS: `ipconfig getifaddr en0` (Wi-Fi) or `en1`
2. On the phone (same Wi-Fi), open:
   - With proxy (recommended): `https://<host-lan-ip>:8443` — accept the local
     CA / install Caddy's root cert via `caddy trust`, then log in.
   - Trusted-LAN no-proxy: `http://<host-lan-ip>:<BUD_PORT>`.
3. BUD's UI is phone-friendly: below 768px the sidebar collapses into a hamburger
   menu (bud-enz) so every top-level page is reachable on a phone.
4. Optional: "Add to Home Screen" in Safari for an app-like launcher. Consider a
   DHCP reservation for the server so its IP doesn't change.

## 6. Back up your data

Everything is one SQLite file (plus WAL/SHM sidecars while running). Back up the
whole `~/.bud/` directory (or `$BUD_DB_PATH`'s directory).

```bash
# Consistent online snapshot (safe while BUD is running, requires sqlite3 CLI):
sqlite3 ~/.bud/cache.db ".backup '/path/to/backups/bud-$(date +%F).db'"

# Or, with the service stopped, a plain copy is fine:
systemctl --user stop bud.service        # (launchctl unload on macOS)
cp -a ~/.bud "/path/to/backups/bud-$(date +%F)"
systemctl --user start bud.service
```

Schedule it (cron / a systemd timer / launchd) and keep copies off the server.
Restore by stopping BUD and copying a snapshot back to `~/.bud/cache.db` (or
point `BUD_DB_PATH` at it). Remember the DB is `0600` and `~/.bud` is `0700` —
preserve those modes on restored copies (`cp -a` does).

## Checklist

- [ ] SPA built (`npm run build`) and `uv sync` run on the server
- [ ] BUD runs headless on loopback via systemd/launchd, survives reboot
- [ ] Reverse proxy (auth + TLS) in front per access-control.md
- [ ] iPhone reaches it over the LAN and can navigate every page
- [ ] Automated, off-server backups of `~/.bud/` scheduled and test-restored
