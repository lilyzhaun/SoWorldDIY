# 3HK Assistant

3HK Assistant 是一个面向 3HK / SoSIM / SIMWorld 储值卡账号的自托管管理工具。项目由 React + Vite 前端、FastAPI 后端和 Redis 会话存储组成，后端负责登录会话、鉴权码、3HK/SIMWorld 接口代理、套餐购买、换号、资源转移、收件箱和交易记录等功能。

本项目不是 3HK、SoSIM 或 SIMWorld 的官方产品。使用者需要自行确认账号、套餐、支付、号码和数据转移操作的风险，并遵守相关服务条款。

## 功能概览

- 多账号登录与会话管理，支持密码登录和 OTP 登录。
- Redis 保存服务端 session，前端通过 `session_id` Cookie 访问当前账号。
- 鉴权码控制登录入口，可通过 CLI 创建、导入、列出和撤销。
- 查看账号资料、套餐、钱包余额、收件箱和交易记录。
- 购买增值套餐、购买 CMN 换号套餐、获取候选号码、执行资源转移。
- 前端 PWA 双入口：登录页和主控制台。
- 可选 external_delivery 通知，用于登录和购买事件提醒。

## 快速开始

### 环境要求

- Python 3.11 或更新版本
- Node.js 18 或更新版本
- Redis 6 或更新版本
- 可访问 3HK/SIMWorld 相关服务的网络环境

### 1. 配置环境变量

```bash
cp .env.example backend/.env
```

至少需要设置：

- `SESSION_SECRET`：服务端 session 与内部维护接口使用的密钥。
- `PASSWORD_ENCRYPTION_KEY`：静默重登密码加密密钥；为空时回退到 `SESSION_SECRET`。
- `REDIS_URL`：Redis 连接地址。
- `REDIS_SESSION_PREFIX`：Redis session key 前缀。
- `PROXY_URL`：访问 3HK/SIMWorld 上游接口时使用的 HTTP/HTTPS 代理；为空则直连。
- `external_delivery_token` / `external_delivery_target`：可选通知配置，留空即禁用。

不要提交 `backend/.env`、`backend/auth_codes.json` 或任何真实凭据。详细配置见 [配置说明](docs/03-configuration.md)。

### 2. 安装并构建前端

```bash
cd frontend
npm install
npm run build
```

构建产物输出到 `frontend/dist/`，由后端托管。

### 3. 安装并启动后端

```bash
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
./start.sh
```

默认监听 `0.0.0.0:8000`，可通过 `HOST` 和 `PORT` 覆盖：

```bash
HOST=127.0.0.1 PORT=8000 ./start.sh
```

### 4. 创建鉴权码

```bash
cd backend
. .venv/bin/activate
python -m app.auth_cli create YOUR_CODE --limit 10
python -m app.auth_cli list
```

更多鉴权码管理说明见 [鉴权码管理](docs/06-auth-codes.md)。

### 5. 验证服务

```bash
curl http://127.0.0.1:8000/_health
curl http://127.0.0.1:8000/_ready
```

`/_health` 只表示应用进程可响应；`/_ready` 会检查 Redis、前端构建产物、PWA 文件和套餐缓存目录。

## 常用开发命令

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

更多测试说明见 [测试说明](docs/07-testing.md)。

## 文档目录

- [架构说明](docs/01-architecture.md)
- [安装与本地开发](docs/02-setup.md)
- [配置说明](docs/03-configuration.md)
- [入口与运行方式](docs/04-entrypoints.md)
- [API 参考](docs/05-api-reference.md)
- [鉴权码管理](docs/06-auth-codes.md)
- [测试说明](docs/07-testing.md)
- [部署说明](docs/08-deploy.md)
- [安全与运维](docs/09-security-and-operations.md)
- [故障排查](docs/10-troubleshooting.md)
- [贡献指南](CONTRIBUTING.md)
- [安全政策](SECURITY.md)

## 仓库结构

```text
.
├── backend/                 # FastAPI 后端
│   ├── app/                 # 应用代码、配置、会话、鉴权码和安全工具
│   ├── plans_cache/         # 运行时套餐缓存目录，仅保留 .gitkeep
│   ├── requirements.txt     # Python 依赖
│   ├── run.py               # ASGI 入口
│   └── start.sh             # 后端启动脚本
├── frontend/                # React + Vite 前端
│   ├── public/              # PWA manifest、service worker 和静态资源
│   ├── src/                 # 登录页、主页面、API 客户端和样式
│   ├── index.html           # 主控制台入口
│   └── login.html           # 登录页入口
├── deploy/bt/               # 宝塔/虚拟主机遗留部署示例
├── docs/                    # 详细文档
├── .env.example             # 环境变量模板
└── README.md
```

## 发布前检查

- 确认 `backend/.env`、`backend/auth_codes.json`、`frontend/dist/`、`frontend/node_modules/`、`backend/.venv/`、`backend/plans_cache/*.json` 和 `.omo/` 不会进入提交或发布包。
- 如真实凭据曾离开本地可信环境，请轮换 `SESSION_SECRET`、`PASSWORD_ENCRYPTION_KEY`、external_delivery token、Redis 密码和鉴权码。
- 运行后端测试、前端测试、前端构建和凭据扫描。
- 根据需要配置反向代理、TLS、Redis 持久化和备份策略。

## 许可证

本项目使用 [MIT License](LICENSE)。
