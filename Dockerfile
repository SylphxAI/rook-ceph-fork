FROM golang:1.25 AS builder
RUN git clone --depth 1 --branch v1.19.3 https://github.com/rook/rook.git /src
WORKDIR /src

# ============================================================
# FORK PATCH: Make Rook work with external cephadm MONs
# ============================================================

# Patch 1: In mons.Start(), after initClusterInfo, if external MONs
# are already in quorum, write config + return success. Skip all
# MON pod management (canary, assign, start).
RUN sed -i '/log.NamespacedInfo(c.Namespace, logger, "targeting the mon count %d", c.spec.Mon.Count)/,/return c.ClusterInfo, c.startMons(c.spec.Mon.Count)/c\
\t// FORK: If external MONs are already providing quorum, skip all MON pod management.\n\
\t// This enables Rook to manage OSDs while cephadm manages MONs.\n\
\tif len(c.ClusterInfo.Monitors) > 0 {\n\
\t\tlog.NamespacedInfo(c.Namespace, logger, "FORK: %d external MONs detected in ClusterInfo, skipping MON pod management", len(c.ClusterInfo.Monitors))\n\
\t\tif err := c.saveMonConfig(); err != nil {\n\
\t\t\tlog.NamespacedWarning(c.Namespace, logger, "FORK: failed to save mon config, continuing: %v", err)\n\
\t\t}\n\
\t\treturn c.ClusterInfo, nil\n\
\t}\n\
\tlog.NamespacedInfo(c.Namespace, logger, "targeting the mon count %d", c.spec.Mon.Count)\n\
\treturn c.ClusterInfo, c.startMons(c.spec.Mon.Count)' pkg/operator/ceph/cluster/mon/mon.go

# Patch 2: Bypass MGR failure in cluster.go (MGR is also on cephadm)
RUN sed -i 's|return errors.Wrap(err, "failed to start ceph mgr")|logger.Warningf("FORK: MGR failed (%v), continuing with external MGR", err)|' pkg/operator/ceph/cluster/cluster.go
RUN sed -i 's|return errors.Wrap(err, "failed to execute post actions after all the ceph monitors started")|logger.Warningf("FORK: post-mon failed (%v), continuing", err)|' pkg/operator/ceph/cluster/cluster.go
RUN sed -i 's|return errors.Wrap(err, "failed to execute post actions after all the ceph managers started")|logger.Warningf("FORK: post-mgr failed (%v), continuing", err)|' pkg/operator/ceph/cluster/cluster.go

# Patch 3: Prevent MON health check from removing external MONs
RUN sed -i '/mon %q not in source of truth but in quorum, removing/{n;s|if err := c.removeMon(mon.Name); err != nil {|logger.Warningf("FORK: skipping removal of external mon %q (not managed by Rook)", mon.Name); if false \&\& err != nil {|}' pkg/operator/ceph/cluster/mon/health.go

# Patch 4: Never remove external MONs from clusterInfo when out of quorum
RUN sed -i 's|} else if !inQuorum \&\& inInfo {|} else if !inQuorum \&\& inInfo \&\& false /* FORK: never remove external mons */ {|' pkg/operator/ceph/cluster/mon/health.go

# Verify
RUN echo "=== FORK patches ===" && grep -c "FORK:" pkg/operator/ceph/cluster/cluster.go pkg/operator/ceph/cluster/mon/mon.go pkg/operator/ceph/cluster/mon/health.go

RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o /rook ./cmd/rook/

FROM docker.io/rook/ceph:v1.19.3
COPY --from=builder /rook /usr/local/bin/rook
