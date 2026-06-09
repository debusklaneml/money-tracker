# Access Control — security posture before network exposure

> **Status:** documented posture (bud-agl). BUD has **no built-in
> authentication** and serves your full financial history from a local SQLite
> database. Read this before you make BUD reachable from anything other than
> `127.0.0.1`.

## The risk

By default `uv run bud` binds `127.0.0.1` (loopback), so only the host machine
can reach it. The moment you set `BUD_HOST=0.0.0.0` (see the
[self-hosting runbook](./self-hosting.md)), **every device on the network can
read and modify your budget** — there is no login, no token, no TLS. On an
untrusted or shared network that is equivalent to publishing your finances.

## Options considered

| Option | What it is | Verdict |
| --- | --- | --- |
| **(a) LAN-only, network trust** | Bind `0.0.0.0`, rely on the home network being trusted; never port-forward. | Acceptable only on a fully trusted home LAN. No confidentiality from other devices/people on that LAN. Fragile. |
| **(b) Reverse proxy: HTTPS + auth** *(recommended)* | Keep BUD on loopback; put Caddy/nginx in front terminating TLS and enforcing HTTP basic auth. | **Chosen default.** Pragmatic for iPhone-over-LAN: real auth, encrypted in transit, BUD itself never exposed directly. |
| **(c) App-level auth** | Build login/sessions into FastAPI. | Largest change; deferred. Revisit if BUD ever needs multi-user or internet exposure. |

## Decision (the posture)

1. **Default stays loopback.** `BUD_HOST` defaults to `127.0.0.1`. Do not change
   this on the BUD process itself for a persistent deployment.
2. **Never bind `0.0.0.0` raw on an untrusted network.** Direct `0.0.0.0`
   binding is only ever acceptable as a *temporary* convenience on a trusted LAN
   you fully control.
3. **For any persistent / phone-accessible deployment, use option (b):** run BUD
   on loopback and front it with a reverse proxy that enforces HTTPS + basic
   auth. This is the security gate for the self-hosting epic (bud-uwb) — resolve
   it before exposing BUD.

## Recommended setup — Caddy reverse proxy

[Caddy](https://caddyserver.com/) is the least-effort option: one binary, a
three-line config, automatic local HTTPS.

1. Generate a bcrypt-hashed password:

   ```bash
   caddy hash-password --plaintext 'choose-a-strong-password'
   # → $2a$14$....   (copy the whole hash)
   ```

2. `Caddyfile` (BUD stays on loopback `:8000`; Caddy listens on `:8443`):

   ```caddy
   # Reach BUD at https://<host-lan-ip>:8443 from your phone.
   :8443 {
       tls internal                # self-signed local CA (or use a real cert)
       basic_auth {                # Caddy < 2.8 spells this `basicauth`
           you $2a$14$REPLACE_WITH_THE_HASH_FROM_STEP_1
       }
       reverse_proxy 127.0.0.1:8000
   }
   ```

3. Run BUD on loopback (unchanged default) and start Caddy:

   ```bash
   BUD_NO_BROWSER=1 uv run bud        # binds 127.0.0.1:8000
   caddy run --config ./Caddyfile     # or `caddy start` to daemonize
   ```

On the phone, open `https://<host-lan-ip>:8443`, accept the local-CA warning
(or install Caddy's root cert via `caddy trust` on devices you control), and log
in with the basic-auth credentials.

> **nginx alternative:** terminate TLS, add `auth_basic` + an `htpasswd` file,
> and `proxy_pass http://127.0.0.1:8000;`. Equivalent posture, more moving parts.

## Hardening already in place

- **DB file permissions (bud-af3):** `~/.bud/cache.db` (and its WAL/SHM
  sidecars) are created `0600` and `~/.bud` is `0700`, so other local accounts
  on the host cannot read your financial history. A fresh DB is created
  owner-only *before* SQLite opens it, so there is no world-readable window.

## When to revisit

Move to **option (c) app-level auth** if you ever need multiple users, want to
expose BUD beyond the LAN, or no longer want to depend on a separate proxy
process. Until then, option (b) is the documented, working posture.
