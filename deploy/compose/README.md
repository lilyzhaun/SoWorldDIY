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

每次认证抓取都会检查 Redis 与前端文件，更新 `app_redis_ready` 和 `app_ready`。
应用不可达告警使用 Prometheus 自带的 `up`，无需额外的 blackbox exporter。

可选监控镜像从 Prometheus 3.15.0 官方源码与预编译 UI 重建，使用 Go 1.27.3、
`golang.org/x/net` 0.60.0，修复 CVE-2026-78667、CVE-2026-78669、CVE-2026-97031、CVE-2026-111943。
源码、UI 和基础镜像均固定摘要；首次构建需要下载 Go 依赖，编译并发限制为 2，单个 Go 进程的软内存限制为 256 MiB。CI 缓存完整构建层。
官方发布包含上述修复并通过扫描的版本后，可移除 `deploy/monitoring/Dockerfile` 的重建步骤。

监控启动前执行 `promtool check config`，认证头从 `/run/secrets/metrics_secret` 读取，
不将秘密拼接到 YAML。可用 `python scripts/check_deployment.py` 进行隔离回归检查。

升级包含会话 CAS 格式时，先停止旧应用再启动新版本，避免旧版本覆盖新会话。
不要在审计或升级时运行生产 Compose 栈的重建命令；先在独立测试环境验收。
