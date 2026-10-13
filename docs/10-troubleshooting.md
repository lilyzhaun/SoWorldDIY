# 故障排查

> [← 安全与运维](09-security-and-operations.md) · [文档首页 →](README.md)

本页列出常见问题和解决方案。

## 服务无法启动

### `SESSION_SECRET is required`

原因：未设置 `SESSION_SECRET`。

处理：

```bash
cp .env.example backend/.env
```

然后编辑 `backend/.env`。

### `Missing uvicorn in .venv`

原因：后端虚拟环境不存在或未安装依赖。

处理：

```bash
cd backend
python -m venv .venv
. .venv/bin/activate
pip install --require-hashes -r requirements.lock
```

## `/_ready` 返回 503

查看响应中的 `checks` 字段：

- `redis=false`：检查 Redis 是否启动、`REDIS_URL` 是否正确、网络是否可达。
- `frontend_index=false` 或 `frontend_login=false`：运行 `cd frontend && npm run build`。
- `frontend_assets=false`：确认 `frontend/dist/assets/` 存在。
- `frontend_manifest=false` 或 `frontend_sw=false`：确认 PWA 文件已被构建复制。
- `plans_cache_dir=false`：确认 `backend/plans_cache/` 存在。

## 登录失败

- 确认鉴权码存在且未用完：`python -m app.auth_cli list`。
- 密码登录只强制使用 THREE 品牌路径；OTP 登录会先识别账号品牌。
- 检查 `PROXY_URL` 是否需要设置。
- 上游返回 4xx/5xx 时，先确认账号、网络和上游服务状态。

## OTP 无法发送

- 确认 `/api/send-otp` 请求包含 `identifier` 和 `auth_code`。
- 鉴权码发送 OTP 时只校验不消耗，但无效 code 会直接返回错误。
- 检查服务器是否能访问 `www.three.com.hk` 和 `simworld.net`。

## CSRF token invalid

常见原因：

- 页面缓存了旧的 CSRF token。
- Cookie 被浏览器或代理丢弃。
- 跨域或反向代理配置导致 Cookie 域名不匹配。
- Redis session 已过期或被清理。

处理：刷新页面、重新登录，并检查反向代理 Cookie 转发。

## 套餐列表获取失败

- 检查 `backend/plans_cache/` 是否可写。
- 删除对应 `plans_*.json` 缓存后重试。
- 检查账号 session 是否过期。
- 检查上游接口是否暂时不可用。

## CMN 候选号码返回 `Fetch failed`

- 确认账号有换号资格：先调用 `/api/cmn/check`。
- 确认当前订阅 ID 和品牌正确。
- 上游可能限流或拒绝当前请求，稍后重试。
- 后端当前向上游请求并最多返回 9 个去重后的候选号码；具体数量也可能受上游响应影响。

## 前端构建失败

```bash
cd frontend
npm ci
npm audit --audit-level=moderate
npm run format:check
npm run lint
npm run typecheck
npm test
npm run build
```

如果依赖版本异常，删除 `node_modules/` 后重新安装。

## 后端测试缺依赖

后端命令应使用项目虚拟环境：

```bash
cd backend
.venv/bin/pytest
.venv/bin/ruff format --check app tests
.venv/bin/ruff check app tests
```

不要使用未安装项目依赖的系统 Python 直接运行测试。

## 覆盖率或 CI 门禁失败

- 后端：运行 `.venv/bin/pytest --cov=app --cov-branch --cov-fail-under=84`；未重新测量前不要降低 `fail_under`。
- 前端：运行 `npm run test:coverage`；门槛配置在 `frontend/vite.config.ts`。
- Action 未固定：运行 `python3 scripts/check_actions_pinned.py`。
- 文档或安全策略：运行 `python3 scripts/check_docs_consistency.py` 和 `python3 scripts/check_security_policy.py`。

---

[← 安全与运维](09-security-and-operations.md) · [文档首页 →](README.md)
