# Trivy image scan exceptions (accepted)

Scanned image: `3hk-new:local` built from digest-pinned
`python:3.13-slim-bookworm` + `node:24-bookworm` (build stage only).

Application dependency scans (`backend/requirements.txt`, `frontend/package-lock.json`)
reported **0** HIGH/CRITICAL via `trivy fs` and `pip-audit --strict`.

## Accepted base-image OS findings (image scan)

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

Action: bump base digests regularly; do not suppress app-language CVEs without fix/upgrade.
