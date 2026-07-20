# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
- Forbidden external_delivery SDK in core package surface (local delivery_extension seam only)

### Fixed
- Auth-code v2 key parsing hardened against reserved shapes and non-hex digests
- Redis systemd unit uses `Type=simple` without libsystemd notify dependency
- Dependabot pull-request secret scans receive the read-only PR metadata permission required by Gitleaks
- Tag releases select notes from the matching changelog version instead of always using `[Unreleased]`
