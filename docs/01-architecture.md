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

### 入口与组合

- `frontend/login.html` 和 `frontend/src/login.tsx` 挂载登录页。
- `frontend/index.html` 和 `frontend/src/main.tsx` 挂载主控制台。
- `frontend/src/LoginPage.tsx` 处理账号识别、OTP 发送和登录提交。
- `frontend/src/MainPage.tsx` 是主页面容器，组合 `useProfileBootstrap`、`useCmn`、`usePurchaseCart`、`useTransfer` 等 hooks，并渲染 `components/` 下的可复用组件（`PlanList`、`CmnSection`、`CartModalContent`、`TransferModalContent`、`InboxModal` 等）。
- `frontend/src/api/client.ts` 统一为非 GET/HEAD 请求附加 CSRF 头。
- `frontend/public/manifest.json` 和 `frontend/public/sw.js` 提供 PWA 元信息与缓存策略。

### CSS 聚合

前端样式采用分层聚合。功能聚合器主要通过 `@import` 组织子文件，`main.css` 还保留少量全局基础规则：

- `src/styles/main.css` 聚合 `tokens.css`、`layout.css`、`plans.css`、`cmn.css`、`modals.css`，并定义主控制台的全局 box sizing、页面基础布局和 reduced-motion 规则。
- `src/styles/login.css` 聚合 `login/` 下的 4 个子样式表，由登录页加载。
- `src/styles/layout.css` 聚合 `layout/` 下的 shell、responsive、header、footer。
- `src/styles/modals.css` 聚合 `modals/` 下的 11 个弹窗样式表。
- `src/styles/cmn.css` 聚合 `cmn/` 下的 section、numbers、refresh。
- `src/styles/plans.css` 聚合 `plans/` 下的 list、responsive、cards。

`@import` 的子文件顺序即 CSS 级联顺序，后面的规则覆盖前面同优先级的规则。修改 `@import` 顺序会影响覆盖关系，需要谨慎调整。

## 后端

后端位于 `backend/`，使用 FastAPI。

### 应用入口与依赖装配

- `backend/run.py` 导出 `app`，供 Uvicorn 加载。
- `backend/app/main.py` 是应用工厂（`create_app`），负责路由注册、前端构建产物托管和上游接口代理。路由本身不在 `main.py` 中定义，而是拆分到 `backend/app/routes/` 模块。
- `backend/app/main_deps.py` 定义 `MainDepsAdapter`：一个 frozen dataclass，持有对 `app.main` 模块的引用，每个属性都是 `@property`，在每次访问时重新读取源模块的同名属性。这样 `monkeypatch.setattr(main, ...)` 的替换对路由、upstream 和 services 立即可见，不缓存快照。
- `backend/app/routes/deps.py` 定义 `RouteDeps` Protocol，描述路由层需要的依赖接口。`MainDepsAdapter` 结构性满足该 Protocol。
- `backend/app/runtime.py` 在模块导入期装配运行时依赖（Redis 客户端、内存缓存、session_store、auth_code_store、密码加密器等），并定义 `get_cache`/`set_cache`/`delete_cache` 等函数 seam。
- `backend/app/services.py` 通过 `configure_service_deps` 接收一个返回 `ServiceDepsProtocol` 的 provider；需要保持 late-bound 的缓存、账号上下文和通知 seam 通过 `_deps()` 读取，固定运行时常量仍从 `runtime.py` 导入。

### 路由模块

- `routes/system.py` — 健康检查（`/_health`）、就绪检查（`/_ready`）、首页（`/`）、`/manifest.json`、`/sw.js`。
- `routes/auth.py` — 登录、OTP 发送、check-user、登出处理。
- `routes/account_pages.py` — `/main` 和 `/main/{account_id}` 页面路由。
- `routes/profile.py` — `GET /api/profile`，调用 `services_profile.fetch_and_build_profile`。
- `routes/commerce.py` — `GET /api/plans`、`GET /api/balance`、`POST /api/purchase`。
- `routes/cmn.py` — CMN 换号：`GET /api/cmn/check`（资格查询）、`POST /api/cmn/numbers`（候选号码，form 字段并校验 CSRF；不再提供状态变更 GET）、`POST /api/cmn/purchase`（创建换号购买订单，Pydantic 校验请求体）。
- `routes/transfer.py` — `POST /api/sim/transfer`（资源转移，Pydantic 校验请求体）。
- `routes/messages.py` — `GET /api/inbox`（收件箱）和 `GET /api/history`（交易记录）。
- `routes/session.py` — `POST /logout`（CSRF）和 `POST /internal/session-cleanup`（维护入口，恒定时间密钥比较）。

### 服务模块

`services.py` 封装品牌识别、套餐后台刷新和购买通知。业务逻辑按职责拆分到独立模块，每个模块导出 typed 函数和 `TypedDict` / `dataclass` 边界：

- `services_commerce.py` — 套餐购买 payload 构造（`build_plan_purchase_payload`）、CMN 购买 payload 构造（`build_cmn_purchase_payload`）、钱包余额解析（`parse_wallet_balance`）、套餐缓存文件加载（`load_plans_from_cache`）。
- `services_profile.py` — 资料聚合：`fetch_and_build_profile`（按品牌顺序请求 getProfile）、`merge_brand_profile_data`、`build_profile_result`。
- `services_profile_offers.py` — active offer 解析辅助（`build_active_offers`、`safe_date_str`、`fuzzy_time_key`）。
- `services_transfer.py` — 资源转移：DTO offer 选择（`select_dto_offer`）、productId 匹配（`select_transfer_product_id`）、payload 组装（`build_transfer_payload`、`assemble_transfer_payload`）。

### 请求体校验

`backend/app/schemas/requests.py` 定义所有写接口的 Pydantic 请求体模型，所有模型使用 `frozen=True` 和 `extra="ignore"`：

- `CheckUserRequest` — `POST /api/check-user`
- `SendOtpRequest` — `POST /api/send-otp`
- `PurchaseRequest` / `PurchaseItem` — `POST /api/purchase`
- `CmnPurchaseRequest` — `POST /api/cmn/purchase`
- `TransferRequest` — `POST /api/sim/transfer`

### 其他后端模块

- `backend/app/upstream.py` 封装上游请求构造（`make_3hk_request`）和静默重登（`attempt_silent_relogin`），通过 `configure_upstream_deps` 注入 `MainDepsAdapter`。
- `backend/app/upstream_urls.py` 集中定义上游 URL 常量和构造函数（`simworld_url`、`three_offer_url`）。
- `backend/app/responses.py` 定义 JSON 成功/错误/重定向响应函数及其 `Protocol` 类型（`JsonSuccessFn`、`JsonErrorFn`、`UpstreamErrorFn`、`RedirectToLoginFn`）。
- `backend/app/session_store.py` 定义 `SessionContext` 和 `RedisSessionStore`。
- `backend/app/session_utils.py` 定义 `SessionMiddleware`、`SessionStoreProtocol` 和 session 辅助函数（`_require_login`、`_validate_csrf`、`_save_session`、`_clear_session` 等）。
- `backend/app/config.py` 从环境变量和 `backend/.env` 加载配置。
- `backend/app/auth_codes.py` 使用 Redis 存储鉴权码，并可从 `backend/auth_codes.json` 导入初始数据。
- `backend/app/security.py` 负责密码加密和 CSRF token 工具。
- `backend/app/delivery_extension.py` 是通知发送 seam，默认 no-op；部署时可通过 `delivery_extension_local.py` 覆盖。
- `backend/app/cache_store.py` 提供内存缓存。
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
