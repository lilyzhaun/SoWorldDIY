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

监控启动前执行 `promtool check config`，认证头从 `/run/secrets/metrics_secret` 读取，
不将秘密拼接到 YAML。可用 `python scripts/check_deployment.py` 进行隔离回归检查。

升级包含会话 CAS 格式时，先停止旧应用再启动新版本，避免旧版本覆盖新会话。
不要在审计或升级时运行生产 Compose 栈的重建命令；先在独立测试环境验收。
