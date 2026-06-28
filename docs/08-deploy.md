# 部署说明

> [← 测试说明](07-testing.md) · [安全与运维 →](09-security-and-operations.md)

本项目推荐以"前端静态构建 + FastAPI 后端托管"的方式部署。生产环境应放在反向代理后，并启用 TLS。

可参考在线示例：<https://3hk.exesim.com>

## 部署流程

1. 准备 Redis。
2. 准备 `backend/.env`，设置强随机密钥和生产 Redis 地址。
3. 安装后端依赖。
4. 安装并构建前端。
5. 使用 Uvicorn、systemd、进程管理器或容器运行 `backend/run.py` 暴露的 ASGI 应用。
6. 用 Nginx、Caddy 或其他反向代理转发到后端监听端口。

## 构建前端

```bash
cd frontend
npm install
npm run build
```

确保 `frontend/dist/index.html`、`frontend/dist/login.html`、`frontend/dist/manifest.json`、`frontend/dist/sw.js` 和 `frontend/dist/assets/` 存在。

## 启动后端

```bash
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
HOST=127.0.0.1 PORT=8000 ./start.sh
```

生产环境建议只监听内网地址或本机地址，由反向代理对外提供 HTTPS。

## 反向代理建议

- 保留 Cookie 和请求头。
- 转发真实客户端 IP，例如 `X-Forwarded-For`。
- 对 `/internal/session-cleanup` 做网络层限制。
- 不缓存 API 响应。
- 对静态资源可设置缓存策略，但 HTML 导航和 API 应网络优先。

## Redis 运维

- 不要把 Redis 暴露到公网。
- 使用密码或内网访问控制。
- 根据业务需要配置持久化。
- 备份前确认备份文件不会公开。

## 运行时文件

以下文件或目录不应进入发布包：

- `backend/.env`
- `backend/auth_codes.json`
- `backend/auth_code.txt`
- `backend/.venv/`
- `backend/plans_cache/*.json`
- `frontend/node_modules/`
- `frontend/dist/`，除非你的部署流程明确需要打包构建产物
- `.omo/`

## 宝塔/虚拟主机遗留说明

`deploy/bt/` 下保留了宝塔/虚拟主机风格部署的遗留说明。根目录不再保留 `.htaccess` 或 `.user.ini`，避免污染应用代码目录。如果仍使用这类环境，可参考 `deploy/bt/.user.ini.example` 按线上路径手动创建。

## 健康检查

部署后执行：

```bash
curl https://your-domain.example/_health
curl https://your-domain.example/_ready
```

`/_ready` 返回 503 时，按返回的 `checks` 字段排查 Redis、前端构建产物或缓存目录。

---

[← 测试说明](07-testing.md) · [安全与运维 →](09-security-and-operations.md)
