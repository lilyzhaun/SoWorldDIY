# Trivy 镜像扫描策略

Scanned image: `3hk-new:local` built from digest-pinned
`python:3.13-slim-bookworm` + `node:24-bookworm` (build stage only).

历史扫描结论不能代表当前版本。应用依赖以 `backend/requirements.lock` 和
`frontend/package-lock.json` 的实时审计结果为准。

## 历史 OS 发现（不再作为豁免）

Findings originate from Debian bookworm packages shipped in the official
`python:3.13-slim-bookworm` runtime (not from pinned Python app dependencies).

| Package | Severity | Rationale | Expiry / revisit |
| --- | --- | --- | --- |
| `perl-base` and related perl modules | HIGH/CRITICAL | Not used by the app runtime path; present as slim image transitive OS packages. No app code invokes perl. | Revisit on next base-image digest bump |
| `zlib1g` CVE-2023-45853 | CRITICAL | `will_not_fix` upstream for miniunz path; not exercised by app (no zip open of untrusted archives in request path). | Revisit on base-image bump |
| `ncurses-*` | HIGH | Terminal libs unused by headless uvicorn service. | Revisit on base-image bump |
| `util-linux*` | HIGH | Core OS utils; no privileged mount/partition operations in container. | Revisit on base-image bump |

Mitigations in place:

- Non-root UID 10001, `no-new-privileges`
- Loopback-only published app port in Compose
- Redis not published; ACL least-privilege user
- No secrets/local overrides in build context (`.dockerignore` + export scan)

镜像扫描必须以 `exit-code: 1` 阻断有修复的 HIGH/CRITICAL；上述按包名的宽泛接受
不是有效豁免。当前不配置漏洞忽略清单。若新增豁免，必须逐个记录 CVE/GHSA、实际
适用性、理由、责任人和固定到期日，并在 CI 中验证期限；不能豁免整个扫描步骤。
