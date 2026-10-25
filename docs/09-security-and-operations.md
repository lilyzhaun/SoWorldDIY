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

### 登录与并发

- 登录页创建 15 分钟匿名会话和 CSRF Cookie；匿名会话创建按 IP 限流。
- `POST /login` 也校验 CSRF、跨站标志及 Origin；非浏览器客户端必须先获取登录页。
- 登录或添加账号会原子轮换 SID 和 CSRF；旧 SID 立即失效。
- 会话更新使用 Redis Lua 版本检查。已注销会话、已删除账号及旧快照不能重新写回。
- 冲突返回 `409 session_conflict`；前端提示刷新或重新登录，不自动重试购买、换号或转移。
- 资料缓存按 SID 与账号隔离，账号列表从当前会话生成；最多保留 256 项缓存。
- 升级时先停止旧应用写入，再切换新版本。**禁止旧 SETEX 写入版本与新 CAS 版本并行运行**。
- 回滚时先停止新版本；仅处理本项目键。如恢复旧版本，先撤销项目会话并要求重新登录，
  在高优先级漏洞未解决前不要恢复公网访问。

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

- 生产应使用 loopback 专用实例（模板见 `deploy/redis/`），应用用户 `3hk-app` 仅能访问 `session:*`、`cache:*`、`auth_code:v2:*`、`ratelimit:*`、`operation:*`。
- ACL 与配置文件 root-only（0600）；模板中的 `CHANGE_ME_*` 占位符不得以真实密码提交。
- 从共享 Redis 迁出时使用 `python -m app.redis_migrate`；切流与回滚须同时变更 `REDIS_URL` 与 `AUTH_CODE_KEY_MODE`。
- 迁移与运维**禁止**触碰 DB 15，禁止 `FLUSHALL`/`FLUSHDB`。
- 迁移仅接受 DB 0，遇到目标已有键即失败，不覆盖目标。迁移期间停止项目写入；验证
  字符串内容、鉴权码 hash 与剩余 TTL，源键过期或目标内容被篡改均不得报告成功。

## Prometheus 指标

- 端点：`GET /metrics`，鉴权头 `x-metrics-secret`（`METRICS_SECRET`）。
- 禁止在标签中记录账号、电话、鉴权码、品牌、query、原始路径或上游响应体。
- 告警规则模板：`deploy/monitoring/alerts.yml`（readiness、5xx、p95 延迟、限流突增、Redis、进程内存）。

## 速率限制

鉴权入口使用 Redis `ratelimit:` 键做固定窗口限流。标识符仅以 SHA-256 形式进入 Redis key，鉴权码从不进入限流键或日志。

IP 先限流；有效鉴权码之后才消耗目标账号 OTP 配额。无效鉴权码不会增加目标账号
登录失败次数。登录提交仍消耗鉴权码次数，保持原语义。

写请求体上限 64 KiB，逐块读取超时 10 秒。应用最多接纳 32 个普通请求，最多 8 个
同步客户端任务；超过等待限制返回 503。健康探针不等待普通请求配额。

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

参考 Uvicorn 启动方式关闭 access log，防止 URL 中的账号标识被记录。反向代理的
访问日志需要由部署者另行设置脱敏或关闭；应用不能替宿主代理保证这一点。

## CI 供应链

- 第三方 GitHub Actions 固定到 40 位提交 SHA，由 `scripts/check_actions_pinned.py` 检查。
- Dependabot 不自动创建版本更新或安全修复 PR；仓库保留漏洞告警，依赖升级由维护者按需处理。
- CI 执行覆盖率、`pip-audit`、`npm audit`、actionlint、Gitleaks，以及 Trivy 文件系统和镜像扫描。
- 基础镜像 OS 漏洞只有在 `deploy/compose/trivy-exceptions.md` 记录 ID、理由和复查期限后才能例外处理。
- Trivy 对有修复的 HIGH/CRITICAL 返回失败；不使用全局 `exit-code: 0` 豁免。
- CI 与 Release 共用 `.github/workflows/checks.yml`；发布只推送已扫描镜像，不重新构建。
- Linux x86_64/aarch64 使用 `requirements.lock` 和 `--require-hashes` 安装。
- 第三方许可证随前端 `/licenses/` 和镜像 `/app/` 分发，详见 `THIRD_PARTY_NOTICES.md`。

---

[← 部署说明](08-deploy.md) · [故障排查 →](10-troubleshooting.md)
