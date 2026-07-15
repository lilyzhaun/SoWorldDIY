# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Hardened multi-stage container image and Compose stack
- Coverage gates for backend and frontend
- Pinned CI supply-chain checks (actionlint, audits, Trivy, secret scan)
- Tag-driven GitHub Release and GHCR publish workflow (dry-run capable)

### Security
- Redis-backed rate limits and dedicated Redis migration assets
- Protected Prometheus metrics endpoint
- Hardened systemd/logrotate deployment under `/opt/3hk-new`
