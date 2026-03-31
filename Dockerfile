FROM golang:1.25 AS builder
RUN git clone --depth 1 --branch v1.19.3 https://github.com/rook/rook.git /src
WORKDIR /src
# Patch: bypass MON gate, reduce canary retries
RUN sed -i 's/canaryRetries           = 30/canaryRetries           = 1/' pkg/operator/ceph/cluster/mon/mon.go && \
    sed -i 's|return errors.Wrap(err, "failed to start ceph monitors")|logger.Warningf("FORK: MON start failed (%v), bypassing", err); if c.ClusterInfo != nil \&\& c.ClusterInfo.IsInitialized() == nil { logger.Infof("FORK: External MON quorum OK") } else { return errors.Wrap(err, "failed to start ceph monitors") }|' pkg/operator/ceph/cluster/cluster.go && \
    sed -i 's|return errors.Wrap(err, "failed to start ceph mgr")|logger.Warningf("FORK: MGR failed (%v), continuing", err)|' pkg/operator/ceph/cluster/cluster.go && \
    sed -i 's|return errors.Wrap(err, "failed to execute post actions after all the ceph monitors started")|logger.Warningf("FORK: post-mon failed, continuing", err)|' pkg/operator/ceph/cluster/cluster.go && \
    sed -i 's|return errors.Wrap(err, "failed to execute post actions after all the ceph managers started")|logger.Warningf("FORK: post-mgr failed, continuing", err)|' pkg/operator/ceph/cluster/cluster.go
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o /rook ./cmd/rook/

FROM docker.io/rook/ceph:v1.19.3
COPY --from=builder /rook /usr/local/bin/rook
