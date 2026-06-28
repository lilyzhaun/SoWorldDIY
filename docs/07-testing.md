# 测试说明

> [← 鉴权码管理](06-auth-codes.md) · [部署说明 →](08-deploy.md)

本项目包含后端 pytest 测试和前端 Vitest 测试。文档和配置变更后也应运行构建和 lint。

## 后端测试

```bash
cd backend
.venv/bin/pytest
```

当前测试覆盖：

- 路由存在性和 CMN 候选号码请求 URL 回归。
- Redis 鉴权码创建、验证、消耗、撤销和列表。
- 内存缓存行为。
- 密码加密/解密和 CSRF token 比较。

## 后端 lint

```bash
cd backend
.venv/bin/ruff check app tests
```

Ruff 配置位于 `backend/pyproject.toml`。当前规则选择 `E`、`F`、`I`，并忽略 `E501`。

## 前端测试

```bash
cd frontend
npm test
```

当前前端测试覆盖 API 客户端辅助函数：

- 按名称读取 Cookie。
- 在存在 CSRF Cookie 时添加 `x-csrf-token` 头。

## 前端 lint

```bash
cd frontend
npm run lint
```

ESLint 使用 flat config，配置文件为 `frontend/eslint.config.js`。

## 前端构建

```bash
cd frontend
npm run build
```

构建命令会先运行 TypeScript 编译，再运行 Vite 构建。构建结果在 `frontend/dist/`。

## 发布前建议命令

```bash
cd backend && .venv/bin/pytest
cd backend && .venv/bin/ruff check app tests
cd frontend && npm test
cd frontend && npm run lint
cd frontend && npm run build
git diff --check
```

还应检查不应发布的文件：

```bash
git ls-files backend/.env backend/auth_codes.json .omo frontend/dist backend/.venv backend/plans_cache
```

预期只允许出现类似 `backend/plans_cache/.gitkeep` 的占位文件。

---

[← 鉴权码管理](06-auth-codes.md) · [部署说明 →](08-deploy.md)
