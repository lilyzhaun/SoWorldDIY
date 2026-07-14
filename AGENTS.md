# AGENTS.md

## 项目边界

本项目由 FastAPI 后端、React/Vite 前端和 Redis 组成。

- 后端入口：`backend/app/main.py`
- 后端路由：`backend/app/routes/`
- 后端业务逻辑：`backend/app/services*.py`
- 前端页面与组件：`frontend/src/`
- 部署服务：`3hk-new.service`
- 测试说明：`docs/07-testing.md`
- 部署说明：`docs/08-deploy.md`

修改前先阅读相关模块和文档，不得基于猜测改代码。

## external_delivery 通知

严禁把 external_delivery 通知直接接入项目核心源码。

- `backend/app/delivery_extension.py` 必须保持为通用通知 seam，默认 no-op。
- 核心路由、服务和配置不得直接导入 `external_delivery_client`、调用 external_delivery API 或依赖 external_delivery SDK。
- 不得把 `external_delivery_client` 加入公开的 `backend/requirements.txt`。
- 不得提交 Bot Token、Chat ID 或其他通知凭据。
- 允许保留现有 `backend/app/delivery_extension_local.example.py` 作为本地部署模板。
- 本机部署必须通过被 Git 忽略的以下文件接入 external_delivery：
  - `backend/app/delivery_extension_local.py`
  - `backend/requirements-local.txt`
  - `backend/.env`
- 不得提交、覆盖或删除上述本地文件。修改通知 seam 时必须确认本地扩展仍可加载。

## 修改原则

- 保持改动聚焦，不夹带无关重构。
- 优先复用现有架构，不重复实现已有能力。
- 简单、范围明确的任务直接处理，不要启动子代理。
- 只有跨多个复杂模块或确实需要独立调查时才使用子代理，通常最多一个。
- 不得让多个子代理重复扫描、分析或测试同一范围。

## 代码组织

严禁新增巨石文件或把多个职责堆入同一模块。

- 新增生产源码原则上不超过 250 行。
- 现有超过 250 行的文件不得继续无节制增长；新增较大功能时应先拆分职责。
- 小型修复不要求为满足行数而进行无关的大规模重构。
- `backend/app/main.py` 只负责应用工厂、依赖装配和路由注册，不直接实现路由业务。
- 后端路由按领域放入 `backend/app/routes/`，复杂逻辑下沉到独立 service。
- `frontend/src/MainPage.tsx` 应保持为页面组合层，业务状态放入 hooks，展示逻辑放入 components。
- 一个文件只承担一个清晰职责；出现多个无关状态机、业务域或大型组件时必须拆分。
- 测试随对应功能放置，不创建包揽多个领域的超大测试文件。

## 测试策略

不要在编辑过程中反复运行全量测试。默认在一轮整体修改完成后，统一执行一次相关验证。

- 后端修改：运行后端格式、lint、类型检查和 pytest。
- 前端修改：运行前端格式、lint、类型检查、Vitest 和构建。
- 前后端同时修改：分别运行两侧验证。
- 仅修改文档：只需执行 `git diff --check`，无需运行应用测试或重启服务。
- 只有定位测试失败时，才允许重复运行对应的单个测试或最小测试集。
- 依赖审计只在依赖文件或 lockfile 发生变化时运行。

具体命令以 `docs/07-testing.md` 和现有 package 配置为准。

## 每轮工作流程

每一轮修改必须遵循以下顺序：

1. 开始前确认当前分支为 `main`，并检查工作区状态。
2. 如果存在非本轮产生的改动，不得丢弃、覆盖或擅自提交，必须先报告。
3. 完成本轮全部代码和文档修改，中途不要反复运行全量测试。
4. 修改完成后一次性运行与改动范围对应的测试和检查。
5. 测试失败时只修复本轮引入的问题，并运行最小必要验证；最终再运行一次相关完整检查。
6. 测试通过且涉及运行时代码时，更新本机部署：
   - 前端变更需要重新构建 `frontend/dist/`。
   - 后端或前端运行时变更需要重启 `3hk-new.service`。
   - 依赖变化时先更新对应本地依赖。
7. 部署后确认：
   - `systemctl is-active 3hk-new.service`
   - `curl http://127.0.0.1:8888/_health`
   - `curl http://127.0.0.1:8888/_ready`
8. 验证通过后，使用 Conventional Commits 创建一个清晰、可回滚的提交。
9. 最终必须确认：
   - 当前分支是 `main`
   - `git status --short` 没有输出
   - 工作区干净
   - 本地服务处于正常状态

除非用户明确要求，否则只提交 commit，不执行 push。

## Git 与安全

- 禁止使用 `git reset --hard`、强制推送或其他破坏性命令。
- 禁止丢弃用户已有的未提交改动。
- 禁止提交 `.env`、本地通知文件、真实凭据、运行时数据、缓存或构建产物。
- 提交信息遵循 `CONTRIBUTING.md` 中的 Conventional Commits 规范。
- 每轮只创建与本轮目标相关的原子提交。
