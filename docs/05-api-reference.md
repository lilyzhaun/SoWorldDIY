# API 参考

> [← 入口与运行方式](04-entrypoints.md) · [鉴权码管理 →](06-auth-codes.md)

本页列出后端主要 API。除登录前接口外，大多数 API 需要有效 `session_id` Cookie。会修改状态的 JSON 接口还需要 CSRF 头。

## 通用约定

- 成功响应通常包含 `status: "success"`。
- 失败响应通常包含 `status: "error"` 和 `message`；由公开错误目录生成的响应还包含稳定 `code`（如 `invalid_request`、`csrf_invalid`、`internal_error`）。
- 多账号上下文通过 `account_id` 查询参数或请求体字段指定。
- 前端 `apiPostJson` 会自动添加 `x-csrf-token`。
- 访问上游接口失败时，后端返回稳定的公开错误文案，不回传异常详情或上游响应体。

## 公开静态资源

| 路径 | 方法 | 请求 | 说明 |
| --- | --- | --- | --- |
| `/favicon.ico` | GET | 无 | 返回现有 `icon-192.png`，响应类型为 `image/png`。 |

## 登录前接口

| 路径 | 方法 | 请求 | 说明 |
| --- | --- | --- | --- |
| `/api/check-user` | POST | JSON: `identifier` | 调用上游账号识别接口，返回账号品牌。 |
| `/api/send-otp` | POST | JSON: `identifier`, `auth_code` | 验证鉴权码后发送 OTP。 |
| `/login` | POST | Form: `login_type`, `identifier`, `auth_code`, `password` 或 `otp` | 登录账号并写入服务端 session。 |

## 账号资料

| 路径 | 方法 | 请求 | 说明 |
| --- | --- | --- | --- |
| `/api/profile` | GET | Query: `account_id`, 可选 `refresh=true` | 聚合账号、订阅、套餐用量和可转移资源。 |
| `/api/balance` | GET | Query: `account_id`, `subscriptionId` | 查询钱包余额。 |
| `/api/inbox` | GET | Query: `account_id` | 查询收件箱消息并按时间倒序返回。 |
| `/api/history` | GET | Query: `account_id`, `subscriptionId`, `startDate`, `endDate` | 查询交易记录。 |

## 套餐与购买

| 路径 | 方法 | 请求 | 说明 |
| --- | --- | --- | --- |
| `/api/plans` | GET | Query: `account_id`, `subscriptionId`, 可选 `brand` | 获取套餐列表。会使用 `backend/plans_cache/` 缓存。 |
| `/api/purchase` | POST | JSON: `account_id`, `subscriptionId`, `items`, `price`, `txnAmount`, `paymentType`, `new_line` | 创建套餐购买订单，成功时返回 `paymentUrl`。 |

## CMN 换号

| 路径 | 方法 | 请求 | 说明 |
| --- | --- | --- | --- |
| `/api/cmn/check` | GET | Query: `account_id`, `subscriptionId` | 查询是否有 CMN 换号资格。 |
| `/api/cmn/numbers` | POST | Form: `account_id`, `subscriptionId` | 向上游锁定候选号码 15 分钟并返回号码列表。需 CSRF。当前请求上游数量为 9。 |
| `/api/cmn/purchase` | POST | JSON: `account_id`, `subscriptionId`, `selectedNumber`, `offerId`, `price`, `txnAmount`, `paymentType` | 创建换号购买订单，成功时返回 `paymentUrl`。 |

## 资源转移

| 路径 | 方法 | 请求 | 说明 |
| --- | --- | --- | --- |
| `/api/sim/transfer` | POST | JSON: `account_id`, `subscriptionId`, `sourceMsisdn`, `targetMsisdn`, `productFamily`, `userOfferId`, `balanceResourceId`, `unit`, `amount` | 执行数据或语音资源转移。 |

## 会话

| 路径 | 方法 | 请求 | 说明 |
| --- | --- | --- | --- |
| `/logout` | POST | Form 可选: `account_id`；Header: `x-csrf-token`（有 session 时必填） | 退出全部或指定账号。仅 Form 字段携带 `account_id`（不接受 query）。失败响应含稳定 `code`。GET 返回 405。 |

## 维护接口

| 路径 | 方法 | 请求 | 说明 |
| --- | --- | --- | --- |
| `/internal/session-cleanup` | POST | Header: `x-session-secret` | 检查 Redis 可用性。该接口应只允许内部调用。内部密钥比较使用恒定时间比较。 |

## CSRF 说明

登录成功后，后端会设置 `csrf_token` Cookie。前端非 GET/HEAD 请求通过 `x-csrf-token` 发送同一个值。当 `COOKIE_SECURE=true` 时，`session` 与 `csrf_token` 均带 `Secure`。以下接口会校验 CSRF：

- `POST /login`：先请求登录页取得匿名会话及 CSRF，认证成功后 SID 和 CSRF 均轮换。

- `/logout`
- `/api/purchase`
- `/api/cmn/numbers`
- `/api/cmn/purchase`
- `/api/sim/transfer`

如果遇到 `CSRF token invalid`，通常是 Cookie 丢失、旧页面缓存、跨域代理配置错误或用户 session 已失效。

## 速率限制

以下入口启用 Redis 固定窗口限流（`ratelimit:` 键，不含鉴权码明文）：

| 路径 | 限制 |
| --- | --- |
| `POST /api/check-user` | 每 IP 30 次 / 5 分钟 |
| `POST /api/send-otp` | 每标识 3 次 / 10 分钟；每 IP 10 次 / 小时 |
| `POST /login` | 每 IP 10 次 / 15 分钟；每标识失败 5 次 / 15 分钟（成功清除失败桶） |

超限返回 HTTP **429**，JSON `code=rate_limited`，并带整数 `Retry-After` 头。仅当直连对端属于 `TRUSTED_PROXY_IPS`（默认 loopback）时信任 `X-Forwarded-For`。Redis 不可用时 `check-user`、`send-otp` 和 `login` 失败关闭（503）。

无效鉴权码不消耗目标账号失败/OTP 配额。请求体超过 64 KiB 返回 413；读取超时返回
408；会话快照冲突返回 409。敏感操作不会由服务端或前端自动重试。

购买金额与新鲜上游套餐目录核对，数量限 1–99；钱包抵扣不能超过订单或当前可用余额。
换号和资源转移校验订阅归属；转移还校验来源号码、资源、单位及额度。非法或过期请求
返回 400，并且不转发上游写操作。

---

[← 入口与运行方式](04-entrypoints.md) · [鉴权码管理 →](06-auth-codes.md)
