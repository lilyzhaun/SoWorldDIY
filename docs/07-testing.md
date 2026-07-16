# 测试说明

> [← 鉴权码管理](06-auth-codes.md) · [部署说明 →](08-deploy.md)

本项目使用 pytest 和 Vitest。CI（`.github/workflows/ci.yml`）分别执行后端、前端、工作流策略、密钥扫描和容器扫描；托管平台是否将这些检查设为合并前必需状态，由分支保护规则决定。

## 后端 CI gates

后端 CI 运行生产依赖审计、编译、OpenAPI、类型、格式、lint 和覆盖率检查：

```bash
cd backend
.venv/bin/pip-audit -r requirements.txt --strict
.venv/bin/python -m compileall -q app
PYTHONWARNINGS=error .venv/bin/python -c "from app.main import create_app; create_app().openapi()"
basedpyright --project pyrightconfig.json
.venv/bin/ruff format --check app tests
.venv/bin/ruff check app tests
.venv/bin/pytest --cov=app --cov-branch --cov-report=term --cov-fail-under=84
```

- `pip-audit` 检查生产依赖中的已知漏洞。
- `compileall` 确认 `app/` 中的 Python 文件可编译。
- OpenAPI warnings-as-errors 确认路由注册和 schema 生成不产生 warning。
- `basedpyright` 按 `backend/pyrightconfig.json` 执行类型检查。
- Ruff 验证格式与 lint。
- pytest 运行后端测试并执行覆盖率门槛。

## 后端测试结构

```bash
cd backend
.venv/bin/pytest
```

测试按领域拆分，主要包括：

- 路由注册和 HTTP contract（auth、CMN、commerce、profile、transfer、messages、session）。
- 鉴权码、Redis 迁移与 ACL、速率限制、metrics 和 session 存储。
- 服务层、上游请求、缓存、安全边界和运行时 seam。

`tests/contract_support.py` 提供共享的 ASGI 调用辅助。测试文件和数量会持续变化，以测试命令退出状态和覆盖率门槛为准，不在文档中锁定数量。

## 前端 CI gates

前端 CI 运行依赖审计、格式、lint、类型、单元覆盖率和构建：

```bash
cd frontend
npm audit --audit-level=moderate
npm run format:check
npm run lint
npm run typecheck
npm run test:coverage
npm run build
```

`npm run test:coverage` 排除 `tests/browser/**` 并执行 Vitest 覆盖率门槛。`npm run build` 会再次运行类型检查后执行 Vite 构建。

## 前端测试结构

```bash
cd frontend
npm test
```

`npm test` 依次执行：

- `npm run test:unit`：普通单元、组件和 contract 测试，排除 `tests/browser/**`。
- `npm run test:browser`：真实 Chromium 测试，使用 `--no-file-parallelism` 串行执行。

单元测试和组件测试与源码同目录放置（`src/**/*.test.ts` / `src/**/*.test.tsx`）；跨模块 contract 位于 `tests/contracts/`；浏览器测试、共享 harness 和 fixture 位于 `tests/browser/`。

当前覆盖范围包括 API/CSRF、登录、CMN、profile、购买、资源转移、收件箱消毒、dialog 可访问性、组件渲染和浏览器交互。测试文件和数量会持续变化，以命令结果为准。

## 覆盖率门槛

### 后端

- Provider：`pytest-cov==7.1.0`，`backend/pyproject.toml` 启用 branch coverage。
- `[tool.coverage.report] fail_under = 84`。
- 行覆盖率与分支覆盖率都不得低于 70%。

### 前端

- Provider：`@vitest/coverage-v8`，配置位于 `frontend/vite.config.ts`。
- 门槛：lines 83、branches 70、functions 67、statements 79。
- 不得仅为提高数字而排除生产模块，也不得在未重新测量时降低门槛。

## 前端构建

```bash
cd frontend
npm run build
```

构建结果在 `frontend/dist/`，包含 `index.html`、`login.html`、`manifest.json`、`sw.js`、`assets/` 和 `static/`。

## 仓库与供应链检查

从仓库根目录运行：

```bash
python3 scripts/check_actions_pinned.py
python3 scripts/check_release_policy.py
python3 scripts/check_docs_consistency.py
python3 scripts/check_security_policy.py
actionlint -color .github/workflows/*.yml
git diff --check
```

CI 还会运行 Gitleaks、Trivy 文件系统扫描和镜像扫描。发布前确认敏感文件、构建产物、虚拟环境和运行时缓存未被跟踪。

---

[← 鉴权码管理](06-auth-codes.md) · [部署说明 →](08-deploy.md)
