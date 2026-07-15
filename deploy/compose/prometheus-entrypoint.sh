#!/bin/sh
set -eu
SECRET="$(cat /run/secrets/metrics_secret)"
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
    authorization:
      type: ""
YAML
# Prometheus native custom headers (2.45+ experimental / 3.x headers field):
# Fall back to bearer unused; use scrape with http config headers via:
python3 - <<'PY' 2>/dev/null || true
PY
# Use promtool-less approach: write headers via envsubst-like shell
SECRET_ESC=$(printf '%s' "$SECRET" | sed 's/[\\"]/\\&/g')
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
    headers:
      X-Metrics-Secret:
        - "${SECRET_ESC}"
YAML
exec /bin/prometheus --config.file=/tmp/prometheus.yml --storage.tsdb.path=/prometheus --web.enable-lifecycle
