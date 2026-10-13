#!/bin/sh
set -eu
cat > /tmp/prometheus.yml <<YAML
global:
  scrape_interval: 15s
  evaluation_interval: 15s
rule_files:
  - /etc/prometheus/alerts.yml
scrape_configs:
  - job_name: 3hk-new
    metrics_path: /metrics
    static_configs:
      - targets: ["app:8888"]
    http_headers:
      X-Metrics-Secret:
        files:
          - /run/secrets/metrics_secret
YAML
/bin/promtool check config /tmp/prometheus.yml
exec /bin/prometheus --config.file=/tmp/prometheus.yml --storage.tsdb.path=/prometheus --web.enable-lifecycle
