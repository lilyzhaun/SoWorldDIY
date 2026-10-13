# Dedicated Redis (loopback 6380)

Tracked templates for a **project-only** Redis 8 instance used by 3HK Assistant.

## Layout

| File | Purpose |
| --- | --- |
| `redis.conf.example` | Loopback bind, port 6380, AOF/RDB, ACL file path |
| `users.acl.example` | `3hk-app` least-privilege user + optional migrate user |
| `3hk-new-redis.service` | systemd unit template |

Production runtime remains **systemd** (see `docs/08-deploy.md`). Compose images (later task) may reuse these ACL patterns.

## Keyspaces

Application keys on DB **0** only:

- `session:*`
- `cache:*`
- `auth_code:v2:*` (HMAC mode)
- `ratelimit:*` (rate limits)
- `operation:*` (24-hour financial-operation deduplication; required on upgrade)

**Never** inspect or mutate DB **15** during migration.

## Migration CLI

From `backend/` with venv active and `AUTH_CODE_HMAC_KEY` set (≥32 bytes):

```bash
python -m app.redis_migrate plan \
  --source-url redis://127.0.0.1:6379/0 \
  --dest-url redis://127.0.0.1:6380/0

python -m app.redis_migrate apply ...
python -m app.redis_migrate verify ...
python -m app.redis_migrate rollback-plan
```

`plan` prints **counts / prefixes / TTLs only**. Passwords and auth-code values are never printed.

Live cutover steps (generate secrets, dual→hmac, 24h retention) are executed in the rollout task that consumes these assets — not by committing secrets here.

## ACL smoke check

```bash
redis-cli -p 6380 --user 3hk-app -a "$APP_PASSWORD" PING
redis-cli -p 6380 --user 3hk-app -a "$APP_PASSWORD" GET other:x   # expect NOPERM
redis-cli -p 6380 --user 3hk-app -a "$APP_PASSWORD" CONFIG GET dir  # expect NOPERM
```

## systemd note

Use `Type=simple` when Redis is built without libsystemd notify support; set `supervised no` in redis.conf.
