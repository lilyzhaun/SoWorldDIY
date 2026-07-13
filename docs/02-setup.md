# 安装与本地开发

> [← 架构说明](01-architecture.md) · [配置说明 →](03-configuration.md)

本文说明从空环境启动 3HK Assistant 的最小流程。

## 准备依赖

需要安装：

- Python 3.11 或更新版本
- Node.js 20.19 或更新版本
- Redis 6 或更新版本
- Git

Redis 需要能被后端访问。默认地址是 `redis://127.0.0.1:6379/0`。

## 克隆仓库

```bash
git clone https://github.com/your-org/3hk_new.git
cd 3hk_new
```

> 可将 URL 替换为你自己 fork 的地址。

## 配置后端环境变量

```bash
cp .env.example backend/.env
```

编辑 `backend/.env`，至少设置强随机的 `SESSION_SECRET` 和 `PASSWORD_ENCRYPTION_KEY`。如果访问上游接口需要代理，设置 `PROXY_URL`。

## 安装后端依赖

```bash
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

## 安装前端依赖并构建

```bash
cd ../frontend
npm ci
npm run build
```

开发模式可以运行：

```bash
npm run dev
```

生产访问路径由 FastAPI 托管 `frontend/dist/`，因此部署前必须先运行 `npm run build`。

## 创建鉴权码

```bash
cd ../backend
. .venv/bin/activate
python -m app.auth_cli create TEST_CODE --limit 10
```

登录页面会要求输入该鉴权码。鉴权码默认写入 Redis，不建议依赖 `backend/auth_codes.json` 作为长期来源。

## 启动后端

```bash
cd backend
./start.sh
```

或者手动运行：

```bash
. .venv/bin/activate
uvicorn run:app --host 0.0.0.0 --port 8000
```

## 本地访问

- 登录页：`http://127.0.0.1:8000/`
- 主控制台：登录后跳转到 `/main/{account_id}`
- 健康检查：`http://127.0.0.1:8000/_health`
- 就绪检查：`http://127.0.0.1:8000/_ready`

## 常见本地问题

- `SESSION_SECRET is required`：没有创建或填写 `backend/.env`。
- `/_ready` 返回 503：检查 Redis 是否可用、前端是否已构建、`frontend/dist/` 是否存在。
- 登录失败：确认鉴权码未用尽、账号信息正确、网络可访问上游服务。

---

[← 架构说明](01-architecture.md) · [配置说明 →](03-configuration.md)
