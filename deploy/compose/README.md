# Compose deployment

1. Copy `env.example` to `.env` in this directory (gitignored via root `.env.*` patterns when named carefully — use `deploy/compose/.env` and pass `--env-file`).

```bash
cp deploy/compose/env.example deploy/compose/.env
# edit secrets (hex passwords recommended for Redis ACL)
docker compose --env-file deploy/compose/.env up -d --build --wait
```

2. App: `http://127.0.0.1:18888` (loopback only). Redis has **no** published port.

3. Metrics: `curl -H "x-metrics-secret: $METRICS_SECRET" http://127.0.0.1:18888/metrics`

4. Optional monitoring profile:

```bash
docker compose --env-file deploy/compose/.env --profile monitoring up -d --wait
```

Prometheus on `http://127.0.0.1:9090` scrapes app metrics with the secret header.
