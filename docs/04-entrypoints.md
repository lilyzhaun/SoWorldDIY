# 入口与运行方式

> [← 配置说明](03-configuration.md) · [API 参考 →](05-api-reference.md)

本项目有后端入口、前端入口、PWA 入口和维护入口。部署时需要理解这些入口的职责边界。

## 后端入口

| 文件 | 作用 |
| --- | --- |
| `backend/run.py` | ASGI 入口，`from app.main import app` 后导出 `app`。Uvicorn 使用 `run:app` 加载它。 |
| `backend/app/__init__.py` | 导出 `app`、`application` 和 `create_app`。 |
| `backend/app/main.py` | 创建 FastAPI 应用（`create_app`），注册路由，托管前端构建产物和 `/static`、`/assets` 挂载点。 |
| `backend/start.sh` | 启动脚本。`cd` 到 `backend/` 后执行 `.venv/bin/uvicorn run:app`，默认监听 `127.0.0.1:8000`。 |

本地开发启动：

```bash
cd backend
HOST=127.0.0.1 PORT=8888 ./start.sh
```

生产环境通过 systemd 管理（见 [部署说明](08-deploy.md)），ExecStart 直接调用 uvicorn 加载 `app.main:app`。

### Uvicorn 加载路径

`run.py` 和 `app.main:app` 指向同一个 ASGI 应用实例。CI 的 OpenAPI 校验和 systemd 的 ExecStart 都使用 `app.main:app` 模块路径；本地开发的 `start.sh` 使用 `run:app`。两者加载的是同一个 `app` 对象。

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

| 路径 | 方法 | 说明 | 定义位置 |
| --- | --- | --- | --- |
| `/` | GET | 登录页或已有账号的主页面跳转入口。带 `?add=1` 时显示新增账号登录页。 | `routes/system.py` |
| `/main` | GET | 登录后跳转到第一个账号。 | `routes/account_pages.py` |
| `/main/{account_id}` | GET | 主控制台页面。 | `routes/account_pages.py` |
| `/logout` | POST | 清理全部账号或指定账号 session。需有效 session 时校验 CSRF；Form 字段可选 `account_id`。 | `routes/session.py` |
| `/manifest.json` | GET | PWA manifest。 | `routes/system.py` |
| `/sw.js` | GET | Service Worker。 | `routes/system.py` |

## 健康检查入口

| 路径 | 方法 | 说明 |
| --- | --- | --- |
| `/_health` | GET | 进程存活检查，返回 `{"status":"ok"}`，不检查外部依赖。 |
| `/_ready` | GET | 就绪检查，检查 Redis ping、`frontend/dist/index.html`、`login.html`、`assets/`、`manifest.json`、`sw.js` 和 `plans_cache/` 目录。任一检查失败返回 503 和 `checks` 字段。 |

## 内部维护入口

| 路径 | 方法 | 说明 |
| --- | --- | --- |
| `/internal/session-cleanup` | POST | 内部维护检查入口，要求请求头 `x-session-secret` 等于 `SESSION_SECRET`，返回 Redis 连通状态。 |

生产环境不应把内部维护入口暴露给不可信网络。反向代理应对该路径做网络层限制。

---

[← 配置说明](03-configuration.md) · [API 参考 →](05-api-reference.md)
