# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- 停止 Dependabot 自动依赖更新 PR，保留仓库漏洞告警，改为维护者按需升级。
- 配套升级 React / React DOM 19.2.7 及类型声明，适配 JSX、可空 ref 与原生布尔 inert 属性。
- 更新 Python 运行依赖、redis-py 8、开发工具和 GitHub Actions，并同步带哈希的运行锁文件。
- 容器使用 Node 26 / Python 3.14，补齐两种 Linux 架构的 Python 3.14 wheel 哈希与 CI 验收。
- Dependabot 将 React、React DOM 和对应类型声明分组更新，避免拆分升级造成版本冲突。

### Security
- 交易接口增加 24 小时 Redis 幂等记录与 `Idempotency-Key`；结果未知时停止重复执行并提示核对。
- 撤销鉴权码不再由启动种子导入恢复，所有模式拒绝将 v2 摘要直接当作鉴权码。
- 常规请求不再回写或清除会话 Cookie，避免旧并发响应覆盖登录轮换结果。
- 更新 Redis、Prometheus 镜像并将 Compose 镜像纳入 CI 漏洞门禁。
- 会话使用 Redis 原子版本检查，阻止旧快照恢复已注销会话和账号；登录轮换 SID/CSRF。
- 登录校验 CSRF 与来源；无效鉴权码不污染目标账号配额，代理链按可信边界解析。
- 资料缓存按会话隔离；请求体、并发和指标标签有界；同步上游请求不阻塞事件循环。
- 敏感写操作核对新鲜上游报价、订阅和资源；会话刷新失败不掩盖已完成操作的结果。
- 更新依赖和基础镜像，运行镜像移除安装工具，Trivy 恢复阻断门禁，无宽泛漏洞豁免。
- 递归排除 `.env`，关闭参考部署的原始访问日志，补充并分发第三方许可证。

### Fixed
- “已订购”补回有效的增值奖赏用量，按实例区分同一套餐的多笔奖赏，避免重复标识和展开联动。
- 修复分类切换清空购物车、新开号码支付金额不一致和带 `+` 邮箱的 URL 编码问题。
- 指标抓取实时刷新 Redis 和应用就绪状态，告警改用实际存在的指标。
- 重写首次部署 README。
- 恢复作者原创 PWA 图标，纠正之前错误的图标来源说明。
- 修复 Prometheus 文件认证头配置和迁移内容/TTL 核验。
- 默认运行遗漏的 `.mjs` 契约测试；CI/Release 共用 Python 3.11–3.14、Node 20.19/24/26 和 Chromium 验收。
- 发布传递同一个已扫描镜像，不在发布步骤重新构建；附带 SBOM。

### Upgrade notes
- 三个交易 POST 接口现在要求 `Idempotency-Key`，前后端须一起升级；自建 Redis ACL 增加 `~operation:*`。
- 迁移保留 `operation:*` 记录；升级或轮换密钥前先核对待确认交易，不要盲目创建新订单。
- 种子导入改为显式 `python -m app.auth_cli seed`，导入后移走种子文件。
- 切换新会话写入逻辑前停止旧版本；禁止旧 SETEX 写入版本与 CAS 版本并行运行。
- 非浏览器登录客户端先获取登录页，携带 CSRF；`409 session_conflict` 需要刷新或重新登录。
- Linux x86_64/aarch64 使用 `pip install --require-hashes -r requirements.lock`。

## [0.1.0] - 2026-07-20

### Added
- Dedicated Redis migration CLI and `deploy/redis/` templates for isolated loopback instances
- Redis-backed endpoint rate limits for auth flows (`ratelimit:` keys)
- Protected Prometheus metrics (`GET /metrics` with `x-metrics-secret`) and alert rule templates
- Multi-stage digest-pinned Dockerfile and Compose stack (app + ACL Redis + optional monitoring)
- Backend/frontend coverage gates (`pytest-cov`, `@vitest/coverage-v8`) with floor thresholds
- CI supply-chain jobs: actionlint, pinned Actions, Dependabot (pip/npm/Docker/Actions), pip-audit, npm audit, Gitleaks, Trivy fs/image
- Tag-driven Release workflow with dry-run, GHCR publish (SBOM/provenance), and GitHub Release notes
- Executable docs/security policy checks: `scripts/check_docs_consistency.py`, `scripts/check_security_policy.py`, `scripts/check_actions_pinned.py`, `scripts/check_release_policy.py`
- Hardened systemd/logrotate/deploy-sync templates targeting `/opt/3hk-new` and `3hk-new` service user

### Changed
- Auth-code Redis keys support staged `legacy|dual|hmac` modes with HMAC-SHA256 fingerprints
- Local service bind defaults to loopback (`127.0.0.1:8888`); container publishes loopback-only on host
- Testing docs document coverage thresholds and how to run `test:coverage`

### Security
- Fail-closed logout storage errors
- HTTP request/response boundary hardening and safe public errors
- Rate-limit identifiers hashed in Redis keys; auth codes never enter limit keys or logs
- Metrics endpoint constant-time secret check; 404 when secret missing, 403 when wrong

### Fixed
- Auth-code v2 key parsing hardened against reserved shapes and non-hex digests
- Redis systemd unit uses `Type=simple` without libsystemd notify dependency
- Dependabot pull-request secret scans receive the read-only PR metadata permission required by Gitleaks
- Tag releases select notes from the matching changelog version instead of always using `[Unreleased]`
