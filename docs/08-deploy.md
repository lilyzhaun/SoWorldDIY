# 部署说明

> [← 测试说明](07-testing.md) · [安全与运维 →](09-security-and-operations.md)

本项目推荐以"前端静态构建 + FastAPI 后端托管"的方式部署。生产环境应放在反向代理后，并启用 TLS。

可参考在线示例：<https://3hk.exesim.com>

## 部署流程

1. 准备 Redis。
2. 准备 `backend/.env`，设置强随机密钥和生产 Redis 地址。
3. 安装后端依赖（`pip install -r requirements.txt`）。
4. 安装并构建前端（`npm ci && npm run build`）。
5. 用 systemd 或进程管理器运行 Uvicorn，监听本机端口。
6. 用 Nginx、Caddy 或其他反向代理转发到后端监听端口，对外提供 HTTPS。

## 构建前端

```bash
cd frontend
npm ci
npm run build
```

确保 `frontend/dist/index.html`、`frontend/dist/login.html`、`frontend/dist/manifest.json`、`frontend/dist/sw.js`、`frontend/dist/assets/` 和 `frontend/dist/static/` 存在。

## 启动后端

### 本地开发

```bash
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
HOST=127.0.0.1 PORT=8888 ./start.sh
```

`start.sh` 默认监听 `127.0.0.1:8000`，可用 `HOST` 和 `PORT` 环境变量覆盖。生产环境必须只监听本机地址，由反向代理对外提供 HTTPS。

### systemd 生产部署（硬化模板）

仓库提供 hardened 单元与日志轮转定义（**不**以 root / `0.0.0.0` 运行）：

| 文件 | 用途 |
| --- | --- |
| `deploy/systemd/3hk-new.service` | 应用单元：`User=3hk-new`，`127.0.0.1:8888`，资源上限与沙箱 hardening |
| `deploy/systemd/3hk-new-redis.service` | 专用 Redis 单元（与 `deploy/redis/` 一致） |
| `deploy/logrotate/3hk-new` | `/var/log/3hk-new/3hk-new.log` 日切、保留 14 天、`copytruncate`、模式 0640 |
| `scripts/deploy_sync.sh` | 将跟踪文件同步到 `/opt/3hk-new`，**字节级保留**本地 `.env` / `delivery_extension_local.py` / `request_overrides_local.py` / `requirements-local.txt` |

同步示例：

```bash
DEST_ROOT=/opt/3hk-new ./scripts/deploy_sync.sh
# 仅预演：
DRY_RUN=1 DEST_ROOT=/tmp/3hk-stage ./scripts/deploy_sync.sh --dry-run
```

关键点：

- 生产 `WorkingDirectory` 为 `/opt/3hk-new/backend`，监听 **127.0.0.1:8888**。
- 依赖 `3hk-new-redis.service`；日志写入 `/var/log/3hk-new/3hk-new.log`。
- 现场切到 `/opt` 与 `3hk-new` 用户属于后续上线步骤（见安全加固 runbook）。

校验：

```bash
systemd-analyze verify deploy/systemd/3hk-new.service deploy/systemd/3hk-new-redis.service
logrotate -d deploy/logrotate/3hk-new
bash -n scripts/deploy_sync.sh backend/start.sh
```

管理命令：

```bash
systemctl daemon-reload
systemctl enable 3hk-new-redis.service 3hk-new.service
systemctl start 3hk-new-redis.service 3hk-new.service
systemctl status 3hk-new.service
```

## 反向代理建议

- 保留 Cookie 和请求头。
- 转发真实客户端 IP，例如 `X-Forwarded-For`。
- 对 `/internal/session-cleanup` 做网络层限制。
- 不缓存 API 响应。
- 对静态资源可设置缓存策略，但 HTML 导航和 API 应网络优先。

## Redis 运维

- 不要把 Redis 暴露到公网。
- 使用密码或内网访问控制。
- 根据业务需要配置持久化。
- 备份前确认备份文件不会公开。

### 专用实例（推荐生产）

仓库提供 `deploy/redis/` 模板，用于在本机 **127.0.0.1:6380** 运行项目专用 Redis 8 实例：

| 文件 | 用途 |
| --- | --- |
| `deploy/redis/redis.conf.example` | 仅绑定回环、AOF/RDB、ACL 文件路径 |
| `deploy/redis/users.acl.example` | `3hk-app` 最小权限用户 + 可选迁移用户（占位密码） |
| `deploy/redis/3hk-new-redis.service` | systemd 单元模板 |
| `deploy/redis/README.md` | 安装与冒烟检查说明 |

应用只使用 DB **0** 的 `session:*`、`cache:*`、`auth_code:v2:*`、`ratelimit:*`。迁移工具**不得**读写 DB **15**。

### 迁移 CLI

在 `backend/` 激活 venv，并设置 `AUTH_CODE_HMAC_KEY`（≥32 字节）后：

```bash
python -m app.redis_migrate plan \
  --source-url redis://127.0.0.1:6379/0 \
  --dest-url redis://127.0.0.1:6380/0
python -m app.redis_migrate apply --source-url ... --dest-url ...
python -m app.redis_migrate verify --source-url ... --dest-url ...
python -m app.redis_migrate rollback-plan
```

`plan` 只输出计数、前缀与 TTL，不打印密码、鉴权码或 key 值。`session:*`/`cache:*` 用 DUMP/PTTL/RESTORE 复制；legacy `auth_code:<code>` 重写为 `auth_code:v2:<hmac>`。回滚时必须**同时**恢复 `REDIS_URL` 与 `AUTH_CODE_KEY_MODE`。

## 健康检查

### 本地检查

```bash
curl http://127.0.0.1:8888/_health
curl http://127.0.0.1:8888/_ready
```

`/_health` 返回 `{"status":"ok"}`，只确认进程存活。`/_ready` 检查 Redis、前端构建产物和缓存目录，任一失败返回 503 和 `checks` 字段。

### 公网检查

```bash
curl https://3hk.exesim.com/_health
curl https://3hk.exesim.com/_ready
```

### PID 检查

确认 systemd 管理的进程正在运行：

```bash
systemctl is-active 3hk-new.service
systemctl status 3hk-new.service
```

`is-active` 返回 `active` 表示进程在运行。`status` 显示 Main PID 和最近日志。

## 回滚

回滚使用 `git revert` 创建反向提交，安全且不丢失历史。**不要使用 `git reset --hard`**，它会丢弃未提交的更改并改写历史，可能导致运行中的服务状态与仓库不一致。

```bash
# 查看最近的提交
git log --oneline -5

# 回滚指定提交
git revert <commit-sha>

# 推送回滚提交
git push

# 重新构建前端（如果前端有变更）
cd frontend && npm run build

# 重启服务以加载后端变更
systemctl restart 3hk-new.service

# 验证
curl http://127.0.0.1:8888/_health
curl http://127.0.0.1:8888/_ready
```

## 运行时文件

以下文件或目录不应进入发布包：

- `backend/.env`
- `backend/auth_codes.json`
- `backend/auth_code.txt`
- `backend/.venv/`
- `backend/plans_cache/*.json`
- `frontend/node_modules/`
- `frontend/dist/`，除非你的部署流程明确需要打包构建产物
- `.omo/`

## 宝塔/虚拟主机遗留说明

`deploy/bt/` 下保留了宝塔/虚拟主机风格部署的遗留说明。根目录不再保留 `.htaccess` 或 `.user.ini`，避免污染应用代码目录。如果仍使用这类环境，可参考 `deploy/bt/.user.ini.example` 按线上路径手动创建。

---

[← 测试说明](07-testing.md) · [安全与运维 →](09-security-and-operations.md)

## Container and GHCR

- Portable stack: `docker compose up -d --wait` (see `docker-compose.yml`; app on `127.0.0.1:18888`).
- Image build: digest-pinned multi-stage `Dockerfile`.
- Releases: semver tags `v*.*.*` run `.github/workflows/release.yml` to publish `ghcr.io/<repository>` with SBOM/provenance. Manual `workflow_dispatch` is dry-run only (no publish).
- Do not bake secrets into images; use Compose env / runtime `.env` outside git.
