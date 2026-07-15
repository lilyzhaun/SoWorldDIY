#!/bin/sh
set -eu
redis-cli --user 3hk-app -a "$REDIS_APP_PASSWORD" --no-auth-warning PING | grep -q PONG
