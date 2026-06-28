# 鉴权码管理

鉴权码用于限制谁可以通过登录页添加账号。它不是 3HK/SIMWorld 的账号密码，而是本应用自己的访问控制层。

## 存储方式

运行时鉴权码存储在 Redis 中，key 前缀由 `AuthCodeStore` 管理。每个鉴权码包含：

- `usage_limit`：允许使用次数。
- `times_used`：已经使用次数。

登录时会校验鉴权码。实际登录提交会消耗使用次数；发送 OTP 时只校验，不消耗。

## CLI 命令

所有命令在 `backend/` 目录运行：

```bash
cd backend
. .venv/bin/activate
```

### 创建或更新鉴权码

```bash
python -m app.auth_cli create CODE --limit 10
```

可指定已使用次数：

```bash
python -m app.auth_cli create CODE --limit 10 --used 2
```

### 列出鉴权码

```bash
python -m app.auth_cli list
```

### 撤销鉴权码

```bash
python -m app.auth_cli revoke CODE
```

### 从文件导入种子

```bash
python -m app.auth_cli seed
```

导入来源是 `backend/auth_codes.json`。该文件是运行时敏感数据，不应提交。

格式示例：

```json
{
  "CODE": {
    "usage_limit": 100,
    "times_used": 0
  }
}
```

## 安全建议

- 生产环境优先用 CLI 直接写入 Redis。
- 不要把真实鉴权码保存在仓库、文档、截图或聊天记录中。
- 发布前确认 `backend/auth_codes.json` 未被跟踪、未被打包。
- 如果怀疑鉴权码泄露，应撤销旧码并创建新码。
- 给临时测试码设置较低的 `usage_limit`。

## 故障排查

- 登录提示鉴权码无效：检查 Redis 是否连接到了正确环境，确认 code 未写错。
- 登录提示鉴权码已用完：使用 `list` 查看 `times_used` 和 `usage_limit`。
- `seed` 没有效果：确认 `backend/auth_codes.json` 存在且 JSON 格式正确。
- Redis 重启后鉴权码丢失：检查 Redis 持久化策略，或重新执行 `create` / `seed`。
