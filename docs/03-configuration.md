# 配置说明

> [← 安装与本地开发](02-setup.md) · [入口与运行方式 →](04-entrypoints.md)

后端配置由 `backend/app/config.py` 加载。启动时会先读取 `backend/.env`，再读取进程环境变量。若同名变量已经存在于进程环境中，`.env` 不会覆盖它。

## 环境变量矩阵

| 变量 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `SESSION_SECRET` | 是 | 无 | 服务端 session、内部维护接口和默认加密回退使用的密钥。必须使用强随机值。 |
| `PASSWORD_ENCRYPTION_KEY` | 否 | `SESSION_SECRET` | session 内密码加密密钥。建议与 `SESSION_SECRET` 使用不同强随机值。 |
| `REDIS_URL` | 否 | `redis://127.0.0.1:6379/0` | Redis 连接地址。生产环境建议使用受控网络和密码。 |
| `REDIS_SESSION_PREFIX` | 否 | `session:` | Redis session key 前缀。多环境共享 Redis 时需要区分。 |
| `PROXY_URL` | 否 | 空 | 访问 3HK/SIMWorld 上游接口时使用的 HTTP/HTTPS 代理。 |
| `CMN_PROXY_URL` | 否 | 空 | CMN 换号接口 (`/mnms/holdAvailableNumbersFor15m/`) 专用代理。仅在该路径的请求上覆盖 `PROXY_URL`，留空则回退到 `PROXY_URL`。 |
| `external_delivery_token` | 否 | 空 | 本地通知扩展 external_delivery Bot Token。仅在 `delivery_extension_local.py` 存在时生效。 |
| `external_delivery_target` | 否 | 空 | 本地通知扩展接收消息的 Chat ID。 |

## `.env` 文件位置

运行时文件路径是 `backend/.env`。根目录 `.env.example` 是模板，不包含真实密钥。

推荐流程：

```bash
cp .env.example backend/.env
```

不要把 `backend/.env` 提交到 Git，也不要把它放入公开发布包。

## 密钥建议

- `SESSION_SECRET` 至少使用 32 字节以上随机值。
- `PASSWORD_ENCRYPTION_KEY` 建议独立生成，不要复用 Redis 密码或其他账号密码。
- 如果密钥曾经进入聊天记录、日志、公开仓库、构建产物或发布包，应立即轮换。

## Redis 配置

Redis 用于保存 session 和鉴权码。生产部署建议：

- 不暴露 Redis 到公网。
- 使用密码或专用内网访问控制。
- 配置持久化或备份，避免重启后 session 和鉴权码全部丢失。
- 按环境设置不同的 `REDIS_SESSION_PREFIX`。

## 代理配置

如果服务器无法直连上游接口，可设置 `PROXY_URL`：

```text
PROXY_URL=http://127.0.0.1:7890
```

该代理会同时用于 HTTP 和 HTTPS 请求。

CMN 换号接口（`/mnms/holdAvailableNumbersFor15m/`）可能需要与通用上游不同的代理（例如地域锁定的住宅代理）。设置 `CMN_PROXY_URL` 即可让该路径的请求使用独立代理：

```text
CMN_PROXY_URL=http://user:pass@proxy.example.com:12321
```

留空时 CMN 请求回退到 `PROXY_URL`。该值仅在本地 `request_overrides_local.py` 存在时生效（参考 `request_overrides_local.example.py` 模板）。

## 通知扩展

通知模块 `backend/app/delivery_extension.py` 默认为 no-op。如需启用本地通知，复制 `backend/app/delivery_extension_local.example.py` 为 `delivery_extension_local.py`，并在 `backend/.env` 中配置 `external_delivery_token` 和 `external_delivery_target`。`delivery_extension_local.py` 已被 `.gitignore` 忽略，不会进入公开仓库。该扩展需要 `external_delivery_client`（见 `requirements-local.txt`）。

---

[← 安装与本地开发](02-setup.md) · [入口与运行方式 →](04-entrypoints.md)
