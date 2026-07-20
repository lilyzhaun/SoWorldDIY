# 贡献指南

感谢你愿意改进 3HK Assistant！欢迎所有形式的贡献：Issue、Pull Request、文档改进、问题排查等。

> 在线示例：<https://3hk.exesim.com>

## 开发环境

推荐按 [安装与本地开发](docs/02-setup.md) 搭建本地环境。你也可以直接参考在线示例：<https://3hk.exesim.com>。

## 分支命名

从 `main` 创建分支，命名格式为 `<type>/<kebab-case-description>`，全部小写：

- `feat/` 新功能
- `fix/` 缺陷修复
- `refactor/` 重构（不改变外部行为）
- `test/` 测试新增或调整
- `docs/` 文档改动
- `chore/` 构建、配置、仓库维护等杂项

示例：`feat/transfer-data-bundle`、`fix/login-otp-timeout`、`chore/repository-standardization`。

## 提交信息

使用 [Conventional Commits](https://www.conventionalcommits.org/) 格式，subject 全小写、祈使语气、不加句号：

```
<type>(<scope>): <subject>
```

- `type` 与分支类型一致：`feat`、`fix`、`refactor`、`test`、`docs`、`chore`、`ci`、`security` 等。
- `scope` 可选，如 `auth`、`cmn`、`commerce`、`profile`、`frontend`。
- `subject` 用简短动宾短语描述变更，不加句号。

示例：`fix: persist successful login session once`、`refactor(cmn): isolate purchase payload construction`、`docs: align architecture and config docs`。

每个提交应是一个清晰、可回滚的原子变更。避免把无关重构混入修复。

## 开发流程

1. 从 `main` 创建符合命名规范的分支。
2. 按 [安装与本地开发](docs/02-setup.md) 完成本地环境配置。
3. 针对行为变更先添加或更新测试。
4. 运行下文列出的全部提交前检查。
5. 确保工作区干净（`git status --short` 无未提交改动）后提交。
6. 提交清晰、可回滚的原子提交。

## 提交前检查

后端 CI gates（与 `.github/workflows/ci.yml` 一致，本地应复现同一组检查）：

```bash
cd backend
.venv/bin/pip-audit -r requirements.txt --strict
.venv/bin/python -m compileall -q app
PYTHONWARNINGS=error .venv/bin/python -c "from app.main import create_app; create_app().openapi()"
basedpyright --project pyrightconfig.json
.venv/bin/ruff format --check app tests
.venv/bin/ruff check app tests
python3.11 -m pytest
python3.12 -m pytest --cov=app --cov-branch --cov-report=term --cov-fail-under=84
```

各 gate 说明：

1. `pip-audit` 检查生产依赖的已知漏洞。
2. `compileall` 确认 `app/` 下所有 Python 文件可编译，无语法错误。
3. OpenAPI warnings-as-errors 以 `PYTHONWARNINGS=error` 调用 `create_app().openapi()`，确保 FastAPI 路由注册不产生 deprecation warning，OpenAPI schema 可正常生成。
4. `basedpyright` 类型检查，配置在 `backend/pyrightconfig.json`，`typeCheckingMode` 为 `basic`，include 范围 `app`，排除 `tests` 和 `.venv`。
5. `ruff format` 和 `ruff check` 验证格式与 lint。
6. Python 3.11 运行完整兼容性测试；Python 3.12 运行相同测试并执行覆盖率门槛。CPython 3.11 会漏报部分异步路径的 trace event，因此覆盖率固定在 Python 3.12 测量。
7. CI 安装 `redis-server` 和 `redis-tools`，确保 Redis 迁移集成测试不会因缺少本地服务端二进制而跳过。

前端 CI gates：

```bash
cd frontend
npm audit --audit-level=moderate
npm run format:check
npm run lint
npm run typecheck
npm run test:coverage
npm run build
```

`npm run test:coverage` 是当前 CI 的测试步骤；本地完整回归可额外运行 `npm test`，它还会执行真实 Chromium 测试。

通用检查：

```bash
git diff --check
git status --short
```

## 工作区要求

提交前工作区必须干净：

- `git status --short` 不应出现未预期的改动。
- `git diff --check` 不应报告空白错误。
- 不要把调试代码、临时文件或注释掉的代码留在提交里。

## 不要提交的内容

敏感文件（已在 `.gitignore` 中忽略，提交前仍需确认）：

- `backend/.env`、`backend/.env.*`（`.env.example` 除外）
- `backend/auth_codes.json`、`backend/auth_code.txt`
- 任何真实账号、密码、OTP、cookies、token 或代理凭据

生成文件与缓存：

- `backend/.venv/`、`__pycache__/`、`.pytest_cache/`、`.mypy_cache/`、`.ruff_cache/`
- `frontend/node_modules/`、`frontend/dist/`、`frontend/.vite/`、`frontend/.eslintcache`
- `backend/plans_cache/*.json`（运行时套餐缓存，仅 `.gitkeep` 需跟踪）
- `*.log`

本地工具与运行时元数据：

- `AGENTS.md`（本机 agent 协作说明，不跟踪）
- `.omo/`
- `.codegraph/`（本地代码索引，不应提交）
- `.opencode/`、`.idea/`、`.vscode/`、`.DS_Store`

本地覆盖文件（可选，不跟踪）：

- `request_overrides_local.py`、`requirements-local.txt`（`request_overrides_local.example.py` 模板可跟踪）

## 代码风格

后端使用 Python 3.11+、FastAPI、Ruff。路由按功能拆分到 `backend/app/routes/*.py`，`main.py` 是应用工厂与路由注册入口，不直接定义路由处理逻辑。开发依赖见 `backend/requirements-dev.txt`（ruff、pytest、basedpyright）。

前端使用 React、TypeScript、Vite、ESLint。`frontend/eslint.config.js` 配置了零 warning 门槛。

保持改动最小，避免把无关重构混入修复。

## 文档责任

改动涉及以下内容时，必须同步更新对应文档：

- 修改 API 行为或新增接口：更新 `docs/05-api-reference.md`。
- 修改或新增配置项：更新 `.env.example` 和 `docs/03-configuration.md`。
- 修改路由结构或模块拆分：更新 `docs/01-architecture.md` 和 `docs/04-entrypoints.md`。
- 修改测试结构或 gate：更新 `docs/07-testing.md`。
- 修改部署流程：更新 `docs/08-deploy.md`。

## Issue 与安全问题

普通缺陷和改进可以通过 Issue 讨论。

**安全问题**请按 [安全政策](SECURITY.md) 的流程私下报告，不要在公开 Issue 中贴出真实凭据或可利用细节。

## 行为准则

参与本项目即表示你同意遵守 [行为准则](CODE_OF_CONDUCT.md)。请在所有交流中保持友善和尊重。

## 覆盖率与供应链门禁

后端覆盖率和生产依赖审计：

```bash
cd backend
python3.11 -m pytest
python3.12 -m pytest --cov=app --cov-branch --cov-report=term --cov-fail-under=84
.venv/bin/pip-audit -r requirements.txt --strict
```

前端覆盖率和依赖审计：

```bash
cd frontend
npm run test:coverage
npm audit --audit-level=moderate
```

仓库策略检查（从仓库根目录运行）：

```bash
python3 scripts/check_actions_pinned.py
python3 scripts/check_release_policy.py
python3 scripts/check_docs_consistency.py
python3 scripts/check_security_policy.py
actionlint -color .github/workflows/*.yml
```

发布时推送语义化版本标签 `vX.Y.Z`，触发 `.github/workflows/release.yml`（GHCR + GitHub Release）。`workflow_dispatch` 只执行 dry-run。发布工作流不得加入 SSH 或 `systemctl` 部署步骤。
