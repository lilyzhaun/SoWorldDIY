#!/bin/sh
set -eu
PASS="${REDIS_APP_PASSWORD:?REDIS_APP_PASSWORD required}"
printf 'user default off\n' > /data/users.acl
printf 'user 3hk-app on >%s ~session:* ~cache:* ~auth_code:v2:* ~ratelimit:* &* +@read +@write +@connection +@scripting +@transaction -@dangerous -config -acl -slowlog\n' "$PASS" >> /data/users.acl
# Point conf aclfile to /data/users.acl via runtime conf
sed 's|aclfile /etc/redis/users.acl|aclfile /data/users.acl|' /etc/redis/redis.conf > /data/redis.conf
exec redis-server /data/redis.conf
