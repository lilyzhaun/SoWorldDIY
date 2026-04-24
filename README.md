# 3HK Assistant

3HK Assistant 是一个面向 3HK / SoSIM / SIMWorld 账号的套餐管理工具。前端使用 React + Vite，后端使用 FastAPI，后端负责会话、鉴权码、代理调用 3HK/SIMWorld 接口、套餐购买、换号、资源转移、收件箱和交易记录等功能。

## 目录结构

```text
.
├── backend/               # FastAPI 后端
│   ├── app/
│   │   ├── __init__.py
│   │   └── main.py        # 后端入口与业务 API
│   ├── plans_cache/       # 运行时套餐缓存目录，仅保留 .gitkeep
│   ├── requirements.txt
│   └── run.py
├── frontend/              # React + Vite 前端
│   ├── public/            # PWA 静态资源
│   ├── src/
│   │   ├── LoginPage.tsx
│   │   ├── MainPage.tsx
│   │   ├── login.tsx
│   │   ├── main.tsx
│   │   └── styles/
│   ├── index.html
│   ├── login.html
│   └── package.json
├── .env.example
└── README.md
```

## 环境要求

- Node.js 18+
- Python 3.11+
- Redis

## 前端工具链

- Vite 8
- TypeScript 6
- ESLint 10 flat config
- Prettier 3

## 配置

复制环境变量示例并按部署环境填写：

```bash
cp .env.example backend/.env
```

关键配置：

- `SESSION_SECRET`：内部清理接口密钥
- `PASSWORD_ENCRYPTION_KEY`：session 内静默重登密码加密密钥；为空时回退使用 `SESSION_SECRET`
- `REDIS_URL`：Redis 连接地址
- `REDIS_SESSION_PREFIX`：Redis session key 前缀
- `PROXY_URL`：访问 3HK/SIMWorld API 使用的 HTTP/HTTPS 代理；为空则直连
- `external_delivery_token` / `external_delivery_target`：购买和登录通知，可留空禁用

鉴权码文件使用 `backend/auth_codes.json`，该文件包含运行态敏感数据，已被 `.gitignore` 忽略。格式示例：

```json
{
  "CODE": {
    "usage_limit": 100,
    "times_used": 0
  }
}
```

鉴权码运行时存储在 Redis，管理命令：

```bash
cd backend
python -m app.auth_cli seed
python -m app.auth_cli create CODE --limit 10
python -m app.auth_cli list
python -m app.auth_cli revoke CODE
```

## 前端开发

```bash
cd frontend
npm install
npm run dev
```

构建：

```bash
npm run build
```

格式化：

```bash
npm run format
```

构建产物输出到 `frontend/dist/`，由后端托管。

## 后端开发

```bash
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn run:app --host 0.0.0.0 --port 8000
```

健康检查：

```bash
curl http://127.0.0.1:8000/_health
curl http://127.0.0.1:8000/_ready
```

代码检查：

```bash
ruff check app
```

## 部署流程

1. 构建前端：`cd frontend && npm run build`
2. 安装后端依赖：`cd backend && pip install -r requirements.txt`
3. 准备 Redis 与 `backend/.env`
4. 通过 `uvicorn run:app` 或进程管理器启动后端

## 仓库规范

- 不提交 `.env`、鉴权码、session、缓存、虚拟环境、`node_modules`、`frontend/dist`。
- 鉴权码运行时存储在 Redis，可通过 `backend/auth_codes.json` 作为启动种子导入；该文件仍为敏感运行态文件，不应提交。
- 当前运行入口是 `backend/app/main.py`，旧 Flask 版本已清理。
- 前端源码位于 `frontend/src`，Vite 使用 `index.html` 与 `login.html` 双入口。
