# 架构说明

> [← 文档首页](README.md) · [安装与本地开发 →](02-setup.md)

3HK Assistant 是一个自托管 Web 应用，核心由浏览器前端、FastAPI 后端、Redis 和 3HK/SIMWorld 上游接口组成。

## 概览

```text
浏览器 / PWA
  │
  │  HTTP + session_id Cookie + CSRF 头
  ▼
FastAPI 后端
  ├── Redis 会话存储
  ├── Redis 鉴权码存储
  └── 本地套餐缓存文件
  ▼
3HK / SoSIM / SIMWorld 上游服务
```

## 组件

前端和后端分别位于独立目录，通过 HTTP 接口协作。

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
- `backend/app/main.py` 是应用工厂（`create_app`），负责路由注册、前端构建产物托管和上游接口代理。路由本身不在 `main.py` 中定义，而是拆分到 `backend/app/routes/` 模块：
  - `routes/system.py` — 健康检查、就绪检查和内部维护入口。
  - `routes/auth.py` — 登录、OTP、登出。
  - `routes/account_pages.py` — 页面路由（`/`、`/main`、`/logout`）。
  - `routes/profile.py` — 资料与套餐用量。
  - `routes/commerce.py` — 套餐购买。
  - `routes/cmn.py` — CMN 换号。
  - `routes/transfer.py` — 资源转移。
  - `routes/messages.py` — 收件箱。
  - `routes/session.py` — 会话管理。
  - `routes/deps.py` — 路由层依赖装配（`RouteDeps`）。
- `backend/app/services.py` 封装 3HK 品牌、套餐缓存和购买通知等服务逻辑。
- `backend/app/upstream.py` 封装上游请求构造和静默重登。
- `backend/app/runtime.py` 在模块导入期装配运行时依赖（Redis、缓存、会话存储等）。
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

后端会访问 `www.three.com.hk` 和 `simworld.net` 的多个接口。项目不与这些服务存在从属或合作关系，部署者需自行承担网络、账号、支付、号码和套餐操作风险。

---

[← 文档首页](README.md) · [安装与本地开发 →](02-setup.md)
