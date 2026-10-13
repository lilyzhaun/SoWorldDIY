#!/usr/bin/env bash
# Initialize least-privilege ACL app user on the CI Redis service.
# Default user remains enabled so GitHub Actions service health-cmd
# (`redis-cli ping`) keeps succeeding for the job lifetime.
set -euo pipefail
HOST="${REDIS_HOST:-127.0.0.1}"
PORT="${REDIS_PORT:-6379}"
APP_PASS="${REDIS_APP_PASSWORD:-ci-redis-app-pass}"

redis-cli -h "$HOST" -p "$PORT" ping | grep -q PONG

redis-cli -h "$HOST" -p "$PORT" ACL SETUSER 3hk-app on \
  ">$APP_PASS" \
  '~session:*' '~cache:*' '~auth_code:v2:*' '~ratelimit:*' '~operation:*' \
  '&*' +@read +@write +@connection +@scripting +@transaction -@dangerous -config -acl -slowlog

redis-cli -h "$HOST" -p "$PORT" --user 3hk-app -a "$APP_PASS" --no-auth-warning PING | grep -q PONG
echo "redis ACL initialized for 3hk-app (default retained for health-cmd)"
