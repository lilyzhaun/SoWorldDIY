# 安全与运维

> [← 部署说明](08-deploy.md) · [故障排查 →](10-troubleshooting.md)

本项目会处理账号登录、上游 cookies、支付跳转、号码和套餐操作。部署前必须把它视为敏感系统管理。

## 敏感数据

以下内容不应提交、公开、截图或写入日志：

- `backend/.env`
- `SESSION_SECRET`
- `PASSWORD_ENCRYPTION_KEY`
- Redis 密码和连接串
- `backend/auth_codes.json`
- 真实鉴权码
- 账号密码、OTP、上游 cookies
- `.omo/` 内部任务与会话工件

## 会话安全

- session 数据保存在 Redis，浏览器只持有 `session` Cookie。
- `session` Cookie 使用 `httponly` 和 `samesite=lax`；当 `COOKIE_SECURE=true` 时，`session` 与 `csrf_token` 均设置 `Secure`。
- CSRF token 存在 session 和 Cookie 中，状态变更请求（含 `/logout`、`POST /api/cmn/numbers`）需要 `x-csrf-token`。
- 公开错误响应使用稳定文案，不返回异常字符串或上游响应体；日志只记录 operation/status/error class/correlation id。
- 如果 `SESSION_SECRET` 泄露，应清理现有 session 并轮换密钥。

## 密码处理

密码登录时，后端会把密码加密后放入 session 数据，用于静默重登。建议：

- 使用独立的 `PASSWORD_ENCRYPTION_KEY`。
- 不要复用其他系统密钥。
- 密钥泄露时清理 Redis session，并要求用户重新登录。

## 鉴权码

鉴权码是应用级入口控制，不等同于用户身份系统。建议：

- 给每个使用者分配独立鉴权码。
- 设置有限使用次数。
- 定期清理不再使用的 code。
- 不把真实 code 写入文档、issue 或聊天记录。
- 生产切到 `hmac` 后使用 `AUTH_CODE_HMAC_KEY` 派生 Redis key；`list` 仅展示 fingerprint。
- `legacy`/`dual` 仅用于迁移窗口；不要把明文 key 当作长期设计。
- 不得在日志、指标或证据文件中记录 `AUTH_CODE_HMAC_KEY` 或鉴权码明文。

## 专用 Redis 与 ACL

- 生产应使用 loopback 专用实例（模板见 `deploy/redis/`），应用用户 `3hk-app` 仅能访问 `session:*`、`cache:*`、`auth_code:v2:*`、`ratelimit:*`。
- ACL 与配置文件 root-only（0600）；模板中的 `CHANGE_ME_*` 占位符不得以真实密码提交。
- 从共享 Redis 迁出时使用 `python -m app.redis_migrate`；切流与回滚须同时变更 `REDIS_URL` 与 `AUTH_CODE_KEY_MODE`。
- 迁移与运维**禁止**触碰 DB 15，禁止 `FLUSHALL`/`FLUSHDB`。

## 速率限制

鉴权入口使用 Redis `ratelimit:` 键做固定窗口限流。标识符仅以 SHA-256 形式进入 Redis key，鉴权码从不进入限流键或日志。

## 上游服务风险

项目会代理访问 3HK/SIMWorld 相关接口，并可能发起购买、换号和资源转移操作。使用者需要自行确认：

- 账号与服务条款允许相关操作。
- 支付跳转和钱包扣款金额正确。
- 换号和资源转移操作不可逆或难以撤销时的风险。
- 代理网络不会泄露账号流量。

## 本地通知扩展

通知模块默认为 no-op。如果你启用了本地通知扩展，消息可能包含账号标识、套餐或购买信息，请确认通知渠道的可见范围和凭据安全。

## 发布前清单

- `git status --short` 中没有未预期文件。
- `git ls-files backend/.env backend/auth_codes.json .omo frontend/dist backend/.venv backend/plans_cache` 不包含敏感运行时文件。
- `.gitignore` 覆盖 `.omo/`、环境文件、鉴权码、缓存、依赖和构建产物。
- 真实凭据未出现在 README、docs、测试、issue 或提交历史中。
- 如凭据曾经外泄，先轮换再发布。

## 日志与排错

日志中不应输出密码、OTP、cookies、鉴权码、账号标识、原始 URL query 或上游响应体。排查问题时优先记录 operation、HTTP 状态、错误类名和 correlation id。

---

[← 部署说明](08-deploy.md) · [故障排查 →](10-troubleshooting.md)
