# syntax=docker/dockerfile:1.7
# Prometheus 3.15.0 security rebuild. Remove this rebuild when an official
# release ships Go >=1.27.2 and golang.org/x/net >=0.60.0 and passes our scan.
FROM golang:1.27.2-bookworm@sha256:5cf287a799e6b94384bad13d16b14904c531f51ba65792237e122ce42b392f61 AS build
ENV CGO_ENABLED=0 GOTOOLCHAIN=local GOWORK=off GOMAXPROCS=2 \
    GOMEMLIMIT=256MiB GOGC=30 GOFLAGS=-p=2
ADD --checksum=sha256:d6383dea2f9b26c1673a52859c453653f2c6c046f7fb6d01db59603a65a732eb \
    https://github.com/prometheus/prometheus/archive/refs/tags/v3.15.0.tar.gz /tmp/source.tar.gz
ADD --checksum=sha256:fa8c918ed05e3f89e232e9b69eccd6ed074602cd9e8a2cab7a92bec9651974ae \
    https://github.com/prometheus/prometheus/releases/download/v3.15.0/prometheus-web-ui-3.15.0.tar.gz /tmp/ui.tar.gz
WORKDIR /src/prometheus
RUN tar -xzf /tmp/source.tar.gz --strip-components=1 -C . \
    && tar -xzf /tmp/ui.tar.gz -C web/ui \
    && bash scripts/compress_assets.sh
RUN --mount=type=cache,target=/go/pkg/mod \
    go get golang.org/x/net@v0.60.0
RUN --mount=type=cache,target=/go/pkg/mod --mount=type=cache,target=/root/.cache/go-build \
    go build -tags netgo,builtinassets -trimpath \
      -ldflags="-s -w -X github.com/prometheus/common/version.Version=3.15.0-security.1 -X github.com/prometheus/common/version.Branch=soworld-security-build" \
      -o /out/prometheus ./cmd/prometheus
RUN --mount=type=cache,target=/go/pkg/mod --mount=type=cache,target=/root/.cache/go-build \
    go build -tags netgo,builtinassets -trimpath \
      -ldflags="-s -w -X github.com/prometheus/common/version.Version=3.15.0-security.1" \
      -o /out/promtool ./cmd/promtool

FROM prom/prometheus:v3.15.0@sha256:efd719c99d83b060d9daefdcf00360461adf279f45ef5391f8d111892118753e
COPY --from=build --chmod=755 /out/prometheus /bin/prometheus
COPY --from=build --chmod=755 /out/promtool /bin/promtool
COPY --from=build /src/prometheus/LICENSE /src/prometheus/NOTICE /usr/share/licenses/prometheus/
