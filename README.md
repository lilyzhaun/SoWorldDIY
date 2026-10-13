<div align="center">

<img src="frontend/public/static/images/icon-192.png" width="88" height="88" alt="SoWorldDIY 图标" />

# SoWorldDIY

**把 3HK、SoSIM 和 SIMWorld 储值卡账号放在同一个自托管面板里。**

[![CI](https://github.com/lilyzhaun/SoWorldDIY/actions/workflows/ci.yml/badge.svg)](https://github.com/lilyzhaun/SoWorldDIY/actions/workflows/ci.yml)
[![MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![React](https://img.shields.io/badge/frontend-React-149eca.svg)](frontend/package.json)
[![FastAPI](https://img.shields.io/badge/backend-FastAPI-009688.svg)](backend/requirements.txt)

[在线示例](https://3hk.exesim.com) · [完整文档](docs/README.md) · [部署说明](docs/08-deploy.md) · [反馈问题](https://github.com/lilyzhaun/SoWorldDIY/issues)

</div>

## 可以做什么

- **多账号管理**：密码或 OTP 登录，切换账号和所属号码。
- **账号概览**：查看套餐用量、有效期、钱包余额和订阅状态。
- **套餐购买**：跨分类选购、购物车结算、余额抵扣和支付跳转。
- **换号与转移**：查询换号资格、选择候选号码、转移数据或语音资源。
- **消息与记录**：查看收件箱和交易历史。
- **手机访问**：响应式界面，支持将 PWA 添加到主屏幕。
- **自托管访问控制**：通过鉴权码限制新增账号登录，提供健康检查和可选监控。

本项目也称 **3HK Assistant**，是独立的社区工具，与 3HK、SoSIM、SIMWorld 无从属或合作关系。功能依赖上游接口和账号资格，上游变更可能影响可用性；请遵守相关服务条款。

## 快速开始：Docker Compose

需要 **Docker Engine、Docker Compose v2、Git 和 Python 3**。以下命令在仓库根目录执行。

### 1. 获取代码

```bash
git clone https://github.com/lilyzhaun/SoWorldDIY.git
cd SoWorldDIY
```

### 2. 生成首次部署配置

下面会创建仅当前用户可读写的配置文件，并生成独立随机密钥；已有配置时会停止，避免覆盖。

```bash
python3 - <<'PY'
import os
import secrets
from pathlib import Path

target = Path("deploy/compose/.env")
text = Path("deploy/compose/env.example").read_text()
keys = {
    "SESSION_SECRET", "PASSWORD_ENCRYPTION_KEY", "AUTH_CODE_HMAC_KEY",
    "METRICS_SECRET", "REDIS_APP_PASSWORD",
}
lines = []
for line in text.splitlines():
    key = line.partition("=")[0]
    lines.append(f"{key}={secrets.token_hex(32)}" if key in keys else line)
fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w") as config:
    config.write("\n".join(lines) + "\n")
print(f"配置已写入 {target}")
PY
```

默认 `COOKIE_SECURE=false`，适合本机 HTTP 访问。通过域名部署时，请配置 HTTPS，并在该文件中设置 `COOKIE_SECURE=true`。代理信任设置见[配置说明](docs/03-configuration.md)。

### 3. 启动应用

```bash
docker compose --env-file deploy/compose/.env up -d --build --wait
curl --fail http://127.0.0.1:18888/_ready
```

打开 **<http://127.0.0.1:18888/>**。应用端口只绑定宿主机回环地址，Redis 不发布宿主机端口。远程访问请通过 HTTPS 反向代理。

### 4. 创建登录所需的鉴权码

```bash
AUTH_CODE="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
docker compose --env-file deploy/compose/.env exec -T app \
  python -m app.auth_cli create "$AUTH_CODE" --limit 10
printf '请保存此鉴权码：%s\n' "$AUTH_CODE"
```

登录页需要同时填写**运营商账号凭据**和**本站鉴权码**。鉴权码的 `--limit` 是登录提交次数，失败的登录提交也可能消耗次数；发送 OTP 只校验、不消耗。默认 HMAC 模式不会保存可恢复的鉴权码明文。

管理命令：

```bash
docker compose --env-file deploy/compose/.env exec app python -m app.auth_cli list
docker compose --env-file deploy/compose/.env exec app python -m app.auth_cli revoke YOUR_CODE
```

## 使用与数据说明

- 账号会话保存在 Redis；用于静默重登的密码通过 Fernet 加密后保存。OTP 不持久保存。
- 会话 Cookie 为 HttpOnly，写请求校验 CSRF；登录成功会旋转会话标识。浏览器登录有效期为 7 天。
- 购买、换号购买和资源转移使用 **24 小时幂等记录**。网络重试沿用同一订单标识，不重复执行同一请求。
- 若显示 **“操作结果待确认”**，请先核对上游交易记录、套餐或资源余额。核对前不要重新创建订单；幂等保护不等于上游事务回滚。
- 种子文件只通过 `python -m app.auth_cli seed` 显式导入，应用启动不会重新导入已撤销的鉴权码。

`.env`、Redis 数据、鉴权码种子和本地代理配置属于部署数据，不应提交到 Git。更多说明见[安全与运维](docs/09-security-and-operations.md)。

## 更新与运维

```bash
git pull --ff-only
docker compose --env-file deploy/compose/.env up -d --build --wait
curl --fail http://127.0.0.1:18888/_ready
```

升级前阅读 [CHANGELOG](CHANGELOG.md)，备份配置和 Redis 数据。Redis 使用命名卷持久化；`docker compose down -v` 会删除该卷。

**从旧版本升级：**自建 Redis ACL 需要增加 `~operation:*` 权限。迁移 Redis 时一并保留 `operation:*` 幂等记录；前后端应一起更新，三个交易接口现在要求 `Idempotency-Key` 请求头。

| 入口 | 用途 |
| --- | --- |
| `GET /_health` | 进程存活检查 |
| `GET /_ready` | Redis 与前端资源就绪检查 |
| `GET /metrics` | Prometheus 指标，需要 `x-metrics-secret` |

可选监控：

```bash
docker compose --env-file deploy/compose/.env --profile monitoring up -d --wait
```

Prometheus 位于 <http://127.0.0.1:9090/>。每次认证抓取会刷新就绪指标；告警规则包含应用不可达、Redis 故障、错误率和延迟。

当前可选监控使用 Prometheus 3.15.0 的安全重建镜像，更新了 Go 与 HTTP/2 依赖；首次构建需要额外时间，详见 [Compose 部署说明](deploy/compose/README.md)。

## 本地开发

运行环境：**Python 3.11+、Node.js 20.19+、Redis 6+**；建议使用当前受支持的 Node.js LTS。完整步骤见[安装与本地开发](docs/02-setup.md)。

```bash
cp .env.example backend/.env
# 编辑 backend/.env：设置随机密钥、METRICS_SECRET、COOKIE_SECURE 和 Redis 地址。

cd frontend
npm ci
npm run build

cd ../backend
python3 -m venv .venv
. .venv/bin/activate
pip install --require-hashes -r requirements.lock
HOST=127.0.0.1 PORT=8888 ./start.sh
```

后端同时托管构建后的前端。开发模式下可以在 `frontend/` 执行 `npm run dev`；API 联调方式见[开发文档](docs/02-setup.md)。

### 验证

```bash
# backend/，使用已激活的虚拟环境
pip install -r requirements-dev.txt
ruff check app tests
ruff format --check app tests
basedpyright --project pyrightconfig.json
python -m pytest

# frontend/
npm run format:check
npm run lint
npm run test:coverage -- --maxWorkers=1 --no-file-parallelism
npm run test:browser
npm run build
```

浏览器测试需要 Chromium，可用 `CHROME_BIN` 指定路径。CI 还执行依赖审计、Git 历史密钥扫描、部署回归，以及应用、Redis、Prometheus 镜像扫描。测试环境和覆盖率规则见[测试说明](docs/07-testing.md)。

## 项目结构

```text
backend/app/      FastAPI 路由、会话、鉴权、上游请求与交易幂等
backend/tests/    后端单元、接口与 Redis 集成测试
frontend/src/    React 页面、业务 hooks 和组件
frontend/tests/  Chromium 回归与界面契约测试
deploy/          Compose、systemd、Redis 和监控配置
docs/            安装、配置、API、部署与运维文档
scripts/         仓库检查、部署同步与发布工具
```

## 文档与贡献

[架构](docs/01-architecture.md) · [配置](docs/03-configuration.md) · [API](docs/05-api-reference.md) · [鉴权码](docs/06-auth-codes.md) · [部署](docs/08-deploy.md) · [故障排查](docs/10-troubleshooting.md)

欢迎通过 Issue 报告问题或提交 Pull Request。请阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 和[行为准则](CODE_OF_CONDUCT.md)。

**安全漏洞请通过 [Security Advisories](https://github.com/lilyzhaun/SoWorldDIY/security/advisories/new) 私密报告**，避免在公开 Issue 中提交凭据或漏洞利用细节。报告方式见 [SECURITY.md](SECURITY.md)。

## 许可证

项目代码按 [MIT License](LICENSE) 发布。第三方依赖遵循各自许可证，详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。运营商名称和商标属于各自权利人。
