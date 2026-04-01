FROM golang:1.25 AS builder
RUN git clone --depth 1 --branch v1.19.3 https://github.com/rook/rook.git /src
WORKDIR /src

# FORK v3: Make Rook work with external cephadm MONs
# Core idea: if MONs already exist in ClusterInfo (from mon-endpoints ConfigMap),
# skip all MON pod management. Just write config and proceed to OSD.

COPY patch.py /tmp/patch.py
RUN python3 /tmp/patch.py

# Verify patches compiled
RUN echo "=== Checking FORK markers ===" && grep -c "FORK:" pkg/operator/ceph/cluster/cluster.go pkg/operator/ceph/cluster/mon/mon.go pkg/operator/ceph/cluster/mon/health.go || true

RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o /rook ./cmd/rook/

FROM docker.io/rook/ceph:v1.19.3
COPY --from=builder /rook /usr/local/bin/rook
