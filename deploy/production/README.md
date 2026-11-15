# Production HTTPS and cookie access gate

This directory is an optional reference profile for running the existing
`deploy/docker-compose.yml` stack behind **TLS** with a **cookie access gate**.
It does not change the application code; it only adds an nginx entrypoint and a
small number of host-mounted files.

The base stack already ships an HTTP-only nginx proxy. Browsers increasingly
intercept plain HTTP before the app loads, and native HTTP Basic Auth prompts
are not shown reliably by every browser or embedded webview. This profile
therefore uses:

- a Let's Encrypt certificate for a real hostname;
- a one-time `/gate?key=...` link that sets a `tx_access` cookie;
- a static `/login.html` instruction page for clients without the cookie;
- an internal-only bypass for Docker SSR traffic so Next.js server components
  can still read the API.

## Prerequisites

- A hostname whose A record points at the server (for evaluation,
  `<ip-with-dashes>.sslip.io` resolves to the IP).
- Ports 80 and 443 reachable from the internet.
- Docker Compose v2.24 or newer (the override uses `!override` for ports).
- `certbot` on the host.

## Setup

```sh
cd deploy

cp production/docker-compose.override.yml.example docker-compose.override.yml
cp production/nginx.gate.conf.example nginx.gate.conf
cp production/login.html login.html

HOST=tianxuan.example.com
TOKEN=$(openssl rand -hex 16)
sed -i "s/__TIANXUAN_HOST__/$HOST/g; s/__ACCESS_TOKEN__/$TOKEN/g" nginx.gate.conf

printf 'access_url=https://%s/gate?key=%s\n' "$HOST" "$TOKEN" > production/access-url.txt
chmod 600 production/access-url.txt
```

Issue the first certificate with the proxy stopped (standalone HTTP-01), then
switch renewal to webroot so the running proxy can serve the challenge:

```sh
docker compose --env-file .env stop proxy
certbot certonly --standalone --non-interactive --agree-tos \
  --register-unsafely-without-email --preferred-challenges http -d "$HOST"
docker compose --env-file .env start proxy

mkdir -p /var/www/certbot
certbot certonly --webroot -w /var/www/certbot -d "$HOST" \
  --non-interactive --agree-tos --force-renewal \
  --deploy-hook "docker exec tianxuan-proxy-1 nginx -s reload"
```

Start the stack and open the one-time link:

```sh
docker compose --env-file .env up -d --build
cat production/access-url.txt
```

`https://<host>/gate?key=<token>` sets a 30-day `tx_access` cookie and redirects
to `/`. After that, `https://<host>/` works directly. Without the cookie, pages
redirect to `/login.html` and `/api/*` returns 401 without a native auth
challenge.

> The base stack publishes `TIANXUAN_HTTP_PORT` (default 8080). The override in
> this directory replaces the proxy `ports` mapping with `80` and `443`; keep the
> hostname in `nginx.gate.conf` in sync with the certificate.

## Files

| File | Purpose |
| --- | --- |
| `nginx.gate.conf.example` | TLS + ACME + cookie-gate nginx config (host/token placeholders) |
| `login.html` | Static instruction page shown without a cookie |
| `docker-compose.override.yml.example` | Adds 80/443 and mounts the config, login page, certificates, ACME webroot |
| `verify.sh` | Read-only smoke check for TLS, gate, pages, API and exports |
| `backup.sh` | Consistent backup of the `tianxuan-data` volume, keeping seven archives |

## Verification

```sh
env TIANXUAN_HOST="$HOST" TIANXUAN_ACCESS_TOKEN_FILE="$PWD/production/access-token" \
  bash production/verify.sh
```

The `verify.sh` script expects the token in `TIANXUAN_ACCESS_TOKEN_FILE` (create it
with `printf '%s' "$TOKEN" > production/access-token; chmod 600 ...`) or in
`TIANXUAN_ACCESS_TOKEN`.

## Security notes

- The access key is a bearer credential: anyone with the link can enter. Treat
  it like a password and rotate it by replacing the token in `nginx.gate.conf`
  and recreating the proxy.
- Keep `production/access-url.txt` out of version control (it is ignored by the
  base `.gitignore` via `deploy/.env`? Add an explicit ignore if needed).
- Native HTTP Basic Auth is intentionally not used; TLS plus the cookie gate is
  the supported reference.
- For a permanent domain, replace the `sslip.io` host, reissue the certificate,
  and rebuild the web image if `NEXT_PUBLIC_TIANXUAN_API_BASE` changes.
