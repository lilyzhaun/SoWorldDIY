# 入口与运行方式

本项目有后端入口、前端入口、PWA 入口和维护入口。部署时需要理解这些入口的职责边界。

## 后端入口

| 文件 | 作用 |
| --- | --- |
| `backend/run.py` | ASGI 入口，导出 `app`。Uvicorn 使用 `run:app` 加载它。 |
| `backend/app/__init__.py` | 导出 `app`、`application` 和 `create_app`。 |
| `backend/app/main.py` | 创建 FastAPI 应用、注册路由、托管前端构建产物、代理上游接口。 |
| `backend/start.sh` | 项目提供的启动脚本，默认运行 `.venv/bin/uvicorn run:app`。 |

默认启动命令：

```bash
cd backend
./start.sh
```

可用环境变量覆盖监听地址：

```bash
HOST=127.0.0.1 PORT=8000 ./start.sh
```

## 前端入口

Vite 配置使用两个 HTML 入口：

| 文件 | 作用 |
| --- | --- |
| `frontend/login.html` | 登录页 HTML。 |
| `frontend/src/login.tsx` | 登录页 React 挂载入口。 |
| `frontend/index.html` | 主控制台 HTML。 |
| `frontend/src/main.tsx` | 主控制台 React 挂载入口。 |

构建命令：

```bash
cd frontend
npm run build
```

构建结果由后端从 `frontend/dist/` 读取。

## Web 路由入口

| 路径 | 方法 | 说明 |
| --- | --- | --- |
| `/` | GET | 登录页或已有账号的主页面跳转入口。带 `?add=1` 时显示新增账号登录页。 |
| `/main` | GET | 登录后跳转到第一个账号。 |
| `/main/{account_id}` | GET | 主控制台页面。 |
| `/logout` | GET | 清理全部账号或指定账号 session。 |
| `/manifest.json` | GET | PWA manifest。 |
| `/sw.js` | GET | Service Worker。 |

## 健康检查入口

| 路径 | 方法 | 说明 |
| --- | --- | --- |
| `/_health` | GET | 进程存活检查，返回 `{"status":"ok"}`。 |
| `/_ready` | GET | 就绪检查，检查 Redis、前端构建产物、PWA 文件和套餐缓存目录。 |

## 内部维护入口

| 路径 | 方法 | 说明 |
| --- | --- | --- |
| `/internal/session-cleanup` | POST | 内部维护检查入口，要求请求头 `x-session-secret` 等于 `SESSION_SECRET`。 |

生产环境不应把内部维护入口暴露给不可信网络。
