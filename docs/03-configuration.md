# 配置说明

后端配置由 `backend/app/config.py` 加载。启动时会先读取 `backend/.env`，再读取进程环境变量。若同名变量已经存在于进程环境中，`.env` 不会覆盖它。

## 环境变量矩阵

| 变量 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `SESSION_SECRET` | 是 | 无 | 服务端 session、内部维护接口和默认加密回退使用的密钥。必须使用强随机值。 |
| `PASSWORD_ENCRYPTION_KEY` | 否 | `SESSION_SECRET` | session 内密码加密密钥。建议与 `SESSION_SECRET` 使用不同强随机值。 |
| `REDIS_URL` | 否 | `redis://127.0.0.1:6379/0` | Redis 连接地址。生产环境建议使用受控网络和密码。 |
| `REDIS_SESSION_PREFIX` | 否 | `session:` | Redis session key 前缀。多环境共享 Redis 时需要区分。 |
| `PROXY_URL` | 否 | 空 | 访问 3HK/SIMWorld 上游接口时使用的 HTTP/HTTPS 代理。 |
| `external_delivery_token` | 否 | 空 | external_delivery Bot token。为空时禁用通知。 |
| `external_delivery_target` | 否 | `0` | external_delivery 管理员 chat id。为空或 0 时不发送通知。 |

## `.env` 文件位置

运行时文件路径是 `backend/.env`。根目录 `.env.example` 是模板，不包含真实密钥。

推荐流程：

```bash
cp .env.example backend/.env
```

不要把 `backend/.env` 提交到 Git，也不要把它放入公开发布包。

## 密钥建议

- `SESSION_SECRET` 至少使用 32 字节以上随机值。
- `PASSWORD_ENCRYPTION_KEY` 建议独立生成，不要复用 external_delivery token、Redis 密码或其他账号密码。
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

## external_delivery 通知

配置 `external_delivery_token` 和 `external_delivery_target` 后，后端会尝试发送登录和购买相关通知。通知失败不会阻止主流程。

如果不需要通知，保持这两个变量为空或默认值即可。
