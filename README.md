<div align="center">

# 3HK Assistant

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Backend: FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![Frontend: React](https://img.shields.io/badge/Frontend-React-61DAFB.svg)](https://react.dev/)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB.svg)](https://www.python.org/)
[![Node.js](https://img.shields.io/badge/Node.js-18+-339933.svg)](https://nodejs.org/)

面向 3HK / SoSIM / SIMWorld 储值卡账号的自托管管理工具

[在线示例](https://3hk.exesim.com) · [文档](docs/README.md) · [贡献指南](CONTRIBUTING.md) · [安全政策](SECURITY.md)

</div>

---

## 简介

3HK Assistant 是一个自托管 Web 应用，帮你集中管理 3HK / SoSIM / SIMWorld 储值卡账号。项目由 React + Vite 前端、FastAPI 后端和 Redis 会话存储组成，后端负责登录会话、鉴权码、3HK/SIMWorld 接口代理、套餐购买、换号、资源转移、收件箱和交易记录等功能。

> ⚠️ 本项目不是 3HK、SoSIM 或 SIMWorld 的官方产品，也不与这些服务存在从属或合作关系。使用者需自行确认账号、套餐、支付、号码和数据转移操作的风险，并遵守相关服务条款。

### 在线示例

- 演示站点：<https://3hk.exesim.com>

## 功能特性

- 🔐 **多账号登录**：支持密码登录和 OTP 登录，服务端 session 由 Redis 管理
- 🎟️ **鉴权码控制**：通过 CLI 创建、导入、列出和撤销访问码
- 📊 **账号概览**：查看资料、套餐用量、钱包余额、收件箱和交易记录
- 🛒 **套餐购买**：购买增值套餐，跳转支付完成后自动刷新
- 📱 **CMN 换号**：查询换号资格、获取候选号码、创建换号订单
- 🔄 **资源转移**：在号码之间转移数据或语音资源
- 📲 **PWA 支持**：双入口 PWA，可安装到手机桌面

## 快速开始

### 环境要求

| 依赖 | 最低版本 | 说明 |
| --- | --- | --- |
| Python | 3.11 | 后端运行时 |
| Node.js | 18 | 前端构建 |
| Redis | 6 | session 和鉴权码存储 |

### 1. 克隆仓库

```bash
git clone https://github.com/your-org/3hk_new.git
cd 3hk_new
```

### 2. 配置环境变量

```bash
cp .env.example backend/.env
```

至少需要设置 `SESSION_SECRET` 和 `PASSWORD_ENCRYPTION_KEY` 为强随机值。完整配置见 [配置说明](docs/03-configuration.md)。

### 3. 构建前端

```bash
cd frontend
npm install
npm run build
```

### 4. 启动后端

```bash
cd ../backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
./start.sh
```

### 5. 创建鉴权码

```bash
python -m app.auth_cli create YOUR_CODE --limit 10
```

### 6. 验证服务

```bash
curl http://127.0.0.1:8000/_health
curl http://127.0.0.1:8000/_ready
```

访问 <http://127.0.0.1:8000/> 即可看到登录页。

## 文档

完整文档位于 [`docs/`](docs/README.md) 目录：

| 文档 | 说明 |
| --- | --- |
| [架构说明](docs/01-architecture.md) | 系统组件、请求流程和外部服务边界 |
| [安装与本地开发](docs/02-setup.md) | 从零搭建开发环境 |
| [配置说明](docs/03-configuration.md) | 环境变量矩阵和密钥建议 |
| [入口与运行方式](docs/04-entrypoints.md) | 后端、前端、Web 路由和维护入口 |
| [API 参考](docs/05-api-reference.md) | 全部 HTTP 接口说明 |
| [鉴权码管理](docs/06-auth-codes.md) | CLI 命令和安全建议 |
| [测试说明](docs/07-testing.md) | 测试命令和覆盖范围 |
| [部署说明](docs/08-deploy.md) | 生产部署、反向代理和运维 |
| [安全与运维](docs/09-security-and-operations.md) | 敏感数据、会话和凭据管理 |
| [故障排查](docs/10-troubleshooting.md) | 常见问题和解决方案 |

## 开发

```bash
# 后端测试和 lint
cd backend && .venv/bin/pytest && .venv/bin/ruff check app tests

# 前端测试、lint 和构建
cd frontend && npm test && npm run lint && npm run build
```

详见 [测试说明](docs/07-testing.md) 和 [贡献指南](CONTRIBUTING.md)。

## 仓库结构

```text
.
├── backend/                 # FastAPI 后端
│   ├── app/                 # 应用代码、配置、会话、鉴权码和安全工具
│   │   ├── main.py          # 应用入口与全部路由
│   │   ├── config.py        # 配置加载
│   │   ├── session_store.py # Redis 会话存储
│   │   ├── auth_codes.py    # 鉴权码存储
│   │   ├── security.py      # 密码加密与 CSRF
│   │   └── auth_cli.py      # 鉴权码 CLI
│   ├── plans_cache/         # 运行时套餐缓存（仅 .gitkeep）
│   ├── requirements.txt
│   ├── run.py               # ASGI 入口
│   └── start.sh             # 启动脚本
├── frontend/                # React + Vite 前端
│   ├── public/              # PWA manifest、service worker
│   ├── src/                 # 登录页、主页面、API 客户端
│   ├── index.html           # 主控制台入口
│   └── login.html           # 登录页入口
├── deploy/bt/               # 宝塔/虚拟主机遗留部署示例
├── docs/                    # 详细文档
├── .github/                 # Issue 模板、PR 模板
├── .env.example             # 环境变量模板
├── CONTRIBUTING.md           # 贡献指南
├── SECURITY.md              # 安全政策
├── CODE_OF_CONDUCT.md       # 行为准则
└── LICENSE                  # MIT 许可证
```

## 发布前检查

- [ ] `backend/.env`、`backend/auth_codes.json`、`.omo/` 不在提交中
- [ ] `frontend/dist/`、`frontend/node_modules/`、`backend/.venv/` 不在提交中
- [ ] 真实凭据未出现在代码、文档、issue 或提交历史中
- [ ] 后端测试、前端测试、lint 和构建全部通过
- [ ] 如凭据曾外泄，已轮换 `SESSION_SECRET`、`PASSWORD_ENCRYPTION_KEY`

## 贡献

欢迎提交 Issue 和 Pull Request。请先阅读 [贡献指南](CONTRIBUTING.md) 和 [行为准则](CODE_OF_CONDUCT.md)。

安全问题请按 [安全政策](SECURITY.md) 私下报告，不要在公开 issue 中披露。

## 许可证

本项目基于 [MIT License](LICENSE) 开源。
