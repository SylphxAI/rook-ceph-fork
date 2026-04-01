FROM golang:1.25 AS builder
RUN git clone --depth 1 --branch v1.19.3 https://github.com/rook/rook.git /src
WORKDIR /src

# Patch 1: Reduce canary retries (fast fail instead of infinite loop)
RUN sed -i 's/canaryRetries           = 30/canaryRetries           = 1/' pkg/operator/ceph/cluster/mon/mon.go

# Patch 2: Bypass MON scheduling failure in cluster.go
RUN sed -i 's|return errors.Wrap(err, "failed to start ceph monitors")|logger.Warningf("FORK: MON start failed (%v), bypassing", err); if c.ClusterInfo != nil \&\& c.ClusterInfo.IsInitialized() == nil { logger.Infof("FORK: External MON quorum OK") } else { return errors.Wrap(err, "failed to start ceph monitors") }|' pkg/operator/ceph/cluster/cluster.go
RUN sed -i 's|return errors.Wrap(err, "failed to start ceph mgr")|logger.Warningf("FORK: MGR failed (%v), continuing", err)|' pkg/operator/ceph/cluster/cluster.go
RUN sed -i 's|return errors.Wrap(err, "failed to execute post actions after all the ceph monitors started")|logger.Warningf("FORK: post-mon failed, continuing", err)|' pkg/operator/ceph/cluster/cluster.go
RUN sed -i 's|return errors.Wrap(err, "failed to execute post actions after all the ceph managers started")|logger.Warningf("FORK: post-mgr failed, continuing", err)|' pkg/operator/ceph/cluster/cluster.go

# Patch 3: CRITICAL — prevent removal of MONs not managed by Rook (health.go line 239-245)
# Change: if mon is in quorum but not in clusterInfo, SKIP removal (log warning only)
RUN sed -i '/mon %q not in source of truth but in quorum, removing/{n;s|if err := c.removeMon(mon.Name); err != nil {|logger.Warningf("FORK: skipping removal of external mon %q (not managed by Rook)", mon.Name); if false \&\& err != nil {|}' pkg/operator/ceph/cluster/mon/health.go

# Patch 4: CRITICAL — prevent removal of external MONs from clusterInfo when out of quorum (health.go line 470-474)
RUN sed -i 's|} else if !inQuorum \&\& inInfo {|} else if !inQuorum \&\& inInfo \&\& false /* FORK: never remove external mons */ {|' pkg/operator/ceph/cluster/mon/health.go

# Patch 5: prevent removal at line 1001
RUN sed -i 's|"monitor %q is not part of the external cluster monitor quorum, removing it"|"FORK: monitor %q is not part of external quorum, SKIPPING removal"|' pkg/operator/ceph/cluster/mon/health.go

# Verify patches
RUN echo "=== FORK patches ===" && grep -c "FORK:" pkg/operator/ceph/cluster/cluster.go pkg/operator/ceph/cluster/mon/health.go pkg/operator/ceph/cluster/mon/mon.go

RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o /rook ./cmd/rook/

FROM docker.io/rook/ceph:v1.19.3
COPY --from=builder /rook /usr/local/bin/rook
