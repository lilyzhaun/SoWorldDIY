# 架构说明

3HK Assistant 是一个自托管 Web 应用，核心由浏览器前端、FastAPI 后端、Redis 和 3HK/SIMWorld 上游接口组成。

## 组件

```text
Browser / PWA
  |
  |  HTTP + session_id cookie + CSRF header
  v
FastAPI backend
  |-- Redis session store
  |-- Redis-backed auth-code store
  |-- local plan cache files
  |-- optional external_delivery events
  v
3HK / SoSIM / SIMWorld upstream services
```

## 前端

前端位于 `frontend/`，使用 React、TypeScript 和 Vite。

- `frontend/login.html` 和 `frontend/src/login.tsx` 挂载登录页。
- `frontend/index.html` 和 `frontend/src/main.tsx` 挂载主控制台。
- `frontend/src/LoginPage.tsx` 处理账号识别、OTP 发送和登录提交。
- `frontend/src/MainPage.tsx` 调用后端 API 展示资料、套餐、余额、收件箱、交易记录，并发起购买、换号和资源转移。
- `frontend/src/api/client.ts` 统一为非 GET/HEAD 请求附加 CSRF 头。
- `frontend/public/manifest.json` 和 `frontend/public/sw.js` 提供 PWA 元信息与缓存策略。

## 后端

后端位于 `backend/`，使用 FastAPI。

- `backend/run.py` 暴露 `app`，供 Uvicorn 加载。
- `backend/app/main.py` 创建应用、注册路由、托管前端构建产物、代理上游接口。
- `backend/app/config.py` 从环境变量和 `backend/.env` 加载配置。
- `backend/app/session_store.py` 使用 Redis 存储 session 数据。
- `backend/app/auth_codes.py` 使用 Redis 存储鉴权码，并可从 `backend/auth_codes.json` 导入初始数据。
- `backend/app/security.py` 负责密码加密和 CSRF token 工具。
- `backend/app/auth_cli.py` 提供鉴权码管理 CLI。

## 会话与鉴权

后端用 `session_id` Cookie 标识服务端 session，真实账号 cookies 和账号上下文保存在 Redis session 数据中。登录表单必须提供鉴权码；鉴权码验证通过后，后端再调用上游登录接口。密码登录时，密码会加密后保存在 session 中，用于静默重登。

CSRF token 存在 session 数据和 `csrf_token` Cookie 中。前端 API 客户端会把 Cookie 中的 token 放入 `x-csrf-token` 请求头。会修改状态的接口会校验该请求头。

## 缓存

后端使用两类缓存：

- Redis session：保存当前浏览器会话、账号上下文和 CSRF token。
- `backend/plans_cache/*.json`：保存不同品牌的套餐列表缓存。该目录只应提交 `.gitkeep`，运行时 JSON 文件不应提交。

## 外部服务边界

后端会访问 `www.three.com.hk` 和 `simworld.net` 的多个接口。项目文档、代码和 UI 应明确这是第三方服务集成，部署者需要自行承担网络、账号、支付、号码和套餐操作风险。
