# 鉴权码管理

> [← API 参考](05-api-reference.md) · [测试说明 →](07-testing.md)

鉴权码用于限制谁可以通过登录页添加账号。它不是 3HK/SIMWorld 的账号密码，而是本应用自己的访问控制层。

## 存储方式

运行时鉴权码存储在 Redis 中，由 `AuthCodeStore` 与 `AUTH_CODE_KEY_MODE` 管理。每个鉴权码 hash 字段包含：

- `usage_limit`：允许使用次数。
- `times_used`：已经使用次数。

### Key 模式（有界迁移）

| 模式 | 读 | 写 | 说明 |
| --- | --- | --- | --- |
| `legacy`（默认） | `auth_code:<code>` | 同左 | 迁移前兼容模式；不需要 `AUTH_CODE_HMAC_KEY`。 |
| `dual` | 优先 `auth_code:v2:<hmac>`，回退 legacy | 仅 v2 | 迁移窗口；要求 `AUTH_CODE_HMAC_KEY`（≥32 字节）。 |
| `hmac` | 仅 v2 | 仅 v2 | 目标模式；拒绝 legacy 明文 key。 |

v2 key 形式为 `auth_code:v2:` + 小写 `HMAC-SHA256(AUTH_CODE_HMAC_KEY, code)` 十六进制摘要。密钥与鉴权码本身永不写入日志。

登录时会校验鉴权码。实际登录提交会消耗使用次数；发送 OTP 时只校验，不消耗。消耗路径在定位到具体 Redis key 后通过 Lua 原子 `HINCRBY` 更新。

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

- `legacy`：输出包含明文 `code` 与计数（兼容迁移前运维习惯）。
- `dual` / `hmac`：只输出稳定的 12 位十六进制 `fingerprint` 与计数，**从不**打印鉴权码本身。`create` 成功时同样只回显 fingerprint。

### 撤销鉴权码

```bash
python -m app.auth_cli revoke CODE
```

`dual` 会同时删除 legacy 与 v2 两个版本的 key。

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

---

[← API 参考](05-api-reference.md) · [测试说明 →](07-testing.md)
