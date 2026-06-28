# 安全与运维

本项目会处理账号登录、上游 cookies、支付跳转、号码和套餐操作。部署前必须把它视为敏感系统管理。

## 敏感数据

以下内容不应提交、公开、截图或写入日志：

- `backend/.env`
- `SESSION_SECRET`
- `PASSWORD_ENCRYPTION_KEY`
- external_delivery Bot token
- Redis 密码和连接串
- `backend/auth_codes.json`
- 真实鉴权码
- 账号密码、OTP、上游 cookies
- `.omo/` 内部任务与会话工件

## 会话安全

- session 数据保存在 Redis，浏览器只持有 `session_id`。
- `session_id` Cookie 使用 `httponly` 和 `samesite=lax`。
- CSRF token 存在 session 和 Cookie 中，非 GET/HEAD 请求需要 `x-csrf-token`。
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

## 上游服务风险

项目会代理访问 3HK/SIMWorld 相关接口，并可能发起购买、换号和资源转移操作。使用者需要自行确认：

- 账号与服务条款允许相关操作。
- 支付跳转和钱包扣款金额正确。
- 换号和资源转移操作不可逆或难以撤销时的风险。
- 代理网络不会泄露账号流量。

## external_delivery 通知

启用 external_delivery 通知时，消息可能包含账号标识、套餐或购买信息。请确认 Bot 和 chat 的可见范围。

## 发布前清单

- `git status --short` 中没有未预期文件。
- `git ls-files backend/.env backend/auth_codes.json .omo frontend/dist backend/.venv backend/plans_cache` 不包含敏感运行时文件。
- `.gitignore` 覆盖 `.omo/`、环境文件、鉴权码、缓存、依赖和构建产物。
- 真实凭据未出现在 README、docs、测试、issue 或提交历史中。
- 如凭据曾经外泄，先轮换再发布。

## 日志与排错

日志中不应输出密码、OTP、cookies 或鉴权码。排查问题时优先记录状态码、请求路径、账号标识的脱敏版本和上游错误摘要。
