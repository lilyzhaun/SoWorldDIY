# 测试说明

> [← 鉴权码管理](06-auth-codes.md) · [部署说明 →](08-deploy.md)

本项目包含后端 pytest 测试和前端 Vitest 测试。CI（`.github/workflows/ci.yml`）对后端和前端分别运行 gates；是否将这些检查设为合并前必需状态，由托管平台的分支保护规则决定。

## 后端 CI gates

后端 CI 按 `.github/workflows/ci.yml` 中的顺序运行以下 6 个 gate。本地开发应复现同一组检查：

```bash
cd backend
.venv/bin/python -m compileall -q app
PYTHONWARNINGS=error .venv/bin/python -c "from app.main import create_app; create_app().openapi()"
basedpyright --project pyrightconfig.json
.venv/bin/ruff format --check app tests
.venv/bin/ruff check app tests
.venv/bin/pytest
```

各 gate 说明：

1. `compileall` — 确认 `app/` 下所有 Python 文件可编译，无语法错误。
2. OpenAPI warnings-as-errors — 以 `PYTHONWARNINGS=error` 调用 `create_app().openapi()`，确保 FastAPI 路由注册不产生 deprecation warning，OpenAPI schema 可正常生成。
3. `basedpyright` — 类型检查，配置在 `backend/pyrightconfig.json`，`typeCheckingMode` 为 `basic`，include 范围 `app`，排除 `tests` 和 `.venv`。`basedpyright` 安装在 `requirements-dev.txt` 中。
4. `ruff format --check app tests` — 验证 Python 格式，配置在 `backend/pyproject.toml`。
5. `ruff check app tests` — lint。当前规则选择 `E`、`F`、`I`、`UP`、`B`，忽略 `E501`。
6. `pytest` — 运行全部后端测试。

## 后端测试结构

```bash
cd backend
.venv/bin/pytest
```

后端测试按职责拆分，每条路由有独立的 contract 测试文件：

| 测试文件                              | 覆盖范围                               |
| ------------------------------------- | -------------------------------------- |
| `test_app_routes.py`                  | 路由存在性和注册                       |
| `test_route_registration_contract.py` | 路由注册契约                           |
| `test_contract_auth.py`               | 登录、OTP、check-user                  |
| `test_contract_cmn.py`                | CMN 换号（GET/POST numbers、purchase） |
| `test_contract_commerce.py`           | 套餐购买、余额查询                     |
| `test_contract_profile.py`            | 资料聚合                               |
| `test_contract_transfer.py`           | 资源转移                               |
| `test_contract_messages.py`           | 收件箱与交易记录                       |
| `test_contract_pages_session.py`      | 页面路由与 session 维护                |
| `test_auth_codes.py`                  | 鉴权码创建、验证、消耗、撤销           |
| `test_security.py`                    | 密码加密/解密和 CSRF token             |
| `test_cache_store.py`                 | 内存缓存行为                           |
| `test_service_helpers.py`             | services 层辅助函数                    |
| `test_main_deps_adapter.py`           | MainDepsAdapter 属性转发               |
| `test_upstream_contract.py`           | upstream 请求构造                      |
| `test_upstream_urls.py`               | URL 常量和构造函数                     |
| `test_delivery_extension.py`                    | 通知 seam                              |

`tests/contract_support.py` 提供 ASGI 调用辅助（`invoke`、`FakeResponse`、`FakeSessionStore`、`authed_request`），各 contract 测试共享这些 fixture 构造请求并断言响应。

当前后端测试基线为 143 个测试（2026-07-13）。测试数量会随新增覆盖而变化，不应作为硬性门槛。

## 前端 CI gates

前端 CI 运行格式、lint、测试和构建 gates：

```bash
cd frontend
npm audit --audit-level=moderate
npm run format:check
npm run lint
npm run typecheck
npm test
npm run build
```

`npm audit --audit-level=moderate` 阻止已知中高危依赖进入分支；`npm run format:check` 验证 Prettier 格式；`npm run lint` 执行 `eslint . --max-warnings 0`；`npm run typecheck` 执行 `tsc --noEmit`。`npm run build` 会再次运行类型检查后执行 Vite 构建。

## 前端测试

```bash
cd frontend
npm test
```

前端使用 Vitest。单元测试和组件测试继续与源码同目录放置（`src/**/*.test.ts` / `src/**/*.test.tsx`）；跨模块源码契约测试位于 `tests/contracts/`；真实 Chromium 测试、共享 harness 和页面 fixture 分别位于 `tests/browser/`、`tests/browser/browserHarness.mjs` 和 `tests/browser/fixtures/`。

`npm test` 依次组合以下两个脚本：

- `npm run test:unit`：运行普通测试并排除 `tests/browser/**`，保留 Vitest 默认文件并行。
- `npm run test:browser`：只运行 `tests/browser/` 下的浏览器测试，并使用 `--no-file-parallelism` 串行执行，避免 Chromium/Vite fixture 之间互相干扰。

当前覆盖范围包括：

- API 客户端 Cookie 读取与 CSRF 头注入。
- CMN hooks（`useCmn`、`useCmnAutoRefresh`、`useCmnEligibility`、`useCmnNumbers`）。
- profile bootstrap 与 refresh 时序。
- purchase cart 数量编辑。
- dialog 可访问性与 focus trap。
- presence value exit 动画。
- 组件渲染（`StatusMessage`、`LoginSuccessStatus`、`UiIcon`、`PresentationSections`、`CartQuantityModal`）。
- CMN 浏览器交互（长按、strict mode、scope）。
- inbox 内容消毒。
- 视觉契约（`tests/contracts/VisualContracts.test.mjs`）。
- feedback 流程（`tests/contracts/FeedbackFlows.test.ts`）。
- mainPage 工具函数。
- CMN 自动刷新与号码模式匹配。

当前前端测试基线为 178 个测试（2026-07-13），21 个测试文件全部通过。

## ESLint 配置

ESLint 使用 flat config，配置文件为 `frontend/eslint.config.js`。

## 前端构建

```bash
cd frontend
npm run build
```

构建命令先运行 TypeScript 编译（`tsc`），再运行 Vite 构建。构建结果在 `frontend/dist/`，包含 `index.html`、`login.html`、`manifest.json`、`sw.js`、`assets/` 和 `static/`。

## 发布前建议命令

后端：

```bash
cd backend && .venv/bin/python -m compileall -q app
cd backend && PYTHONWARNINGS=error .venv/bin/python -c "from app.main import create_app; create_app().openapi()"
cd backend && basedpyright --project pyrightconfig.json
cd backend && .venv/bin/ruff format --check app tests
cd backend && .venv/bin/ruff check app tests
cd backend && .venv/bin/pytest
```

前端：

```bash
cd frontend && npm run format:check
cd frontend && npm audit --audit-level=moderate
cd frontend && npm run lint
cd frontend && npm run typecheck
cd frontend && npm test
cd frontend && npm run build
```

其他检查：

```bash
git diff --check
git ls-files backend/.env backend/auth_codes.json .omo frontend/dist backend/.venv backend/plans_cache
```

预期只允许出现类似 `backend/plans_cache/.gitkeep` 的占位文件。

---

[← 鉴权码管理](06-auth-codes.md) · [部署说明 →](08-deploy.md)
