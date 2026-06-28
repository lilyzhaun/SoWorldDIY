# 贡献指南

感谢你愿意改进 3HK Assistant！欢迎所有形式的贡献：Issue、Pull Request、文档改进、问题排查等。

> 在线示例：<https://3hk.exesim.com>

## 开发环境

推荐按 [安装与本地开发](docs/02-setup.md) 搭建本地环境。你也可以直接参考在线示例：<https://3hk.exesim.com>。

## 开发流程

1. Fork 或创建本地分支。
2. 按 README 完成本地环境配置。
3. 针对行为变更先添加或更新测试。
4. 运行相关测试、lint 和构建。
5. 提交清晰、可回滚的原子提交。

## 提交前检查

后端：

```bash
cd backend
.venv/bin/pytest
.venv/bin/ruff check app tests
```

前端：

```bash
cd frontend
npm test
npm run lint
npm run build
```

通用检查：

```bash
git diff --check
git status --short
```

## 不要提交的内容

- `backend/.env`
- `backend/auth_codes.json`
- `backend/auth_code.txt`
- `backend/.venv/`
- `backend/plans_cache/*.json`
- `frontend/node_modules/`
- `frontend/dist/`
- `.omo/`
- 任何真实账号、密码、OTP、cookies、token 或代理凭据

## 代码风格

- 后端使用 Python 3.11+、FastAPI、Ruff。
- 前端使用 React、TypeScript、Vite、ESLint、Prettier。
- 保持改动最小，避免把无关重构混入修复。
- 修改 API 行为时同步更新 `docs/05-api-reference.md`。
- 修改配置项时同步更新 `.env.example` 和 `docs/03-configuration.md`。

## Issue 与安全问题

普通缺陷和改进可以通过 Issue 讨论。

**安全问题**请按 [安全政策](SECURITY.md) 的流程私下报告，不要在公开 Issue 中贴出真实凭据或可利用细节。

## 行为准则

参与本项目即表示你同意遵守 [行为准则](CODE_OF_CONDUCT.md)。请在所有交流中保持友善和尊重。
