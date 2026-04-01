import re

# ============================================================
# Patch 1: mon.go — skip MON pod management when external MONs exist
# ============================================================
with open("pkg/operator/ceph/cluster/mon/mon.go") as f:
    code = f.read()

# Replace the targeting + startMons block with external MON check
old = '''	log.NamespacedInfo(c.Namespace, logger, "targeting the mon count %d", c.spec.Mon.Count)

	// create the mons for a new cluster or ensure mons are running in an existing cluster
	return c.ClusterInfo, c.startMons(c.spec.Mon.Count)'''

new = '''	// FORK: If external MONs are already providing quorum (from mon-endpoints ConfigMap),
	// skip all MON pod management. This enables Rook to manage OSDs while cephadm manages MONs.
	allMons := c.ClusterInfo.AllMonitors()
	if len(allMons) > 0 {
		log.NamespacedInfo(c.Namespace, logger, "FORK: %d external MONs detected, skipping MON pod management", len(allMons))
		if err := c.saveMonConfig(); err != nil {
			log.NamespacedWarning(c.Namespace, logger, "FORK: failed to save mon config: %v", err)
		}
		return c.ClusterInfo, nil
	}
	log.NamespacedInfo(c.Namespace, logger, "targeting the mon count %d", c.spec.Mon.Count)
	return c.ClusterInfo, c.startMons(c.spec.Mon.Count)'''

code = code.replace(old, new)
with open("pkg/operator/ceph/cluster/mon/mon.go", "w") as f:
    f.write(code)
print("Patched mon.go")

# ============================================================
# Patch 2: cluster.go — bypass MGR + post-action failures
# ============================================================
with open("pkg/operator/ceph/cluster/cluster.go") as f:
    code = f.read()

code = code.replace(
    'return errors.Wrap(err, "failed to start ceph mgr")',
    'logger.Warningf("FORK: MGR failed (%v), continuing with external MGR", err)'
)
code = code.replace(
    'return errors.Wrap(err, "failed to execute post actions after all the ceph monitors started")',
    'logger.Warningf("FORK: post-mon failed (%v), continuing", err)'
)
code = code.replace(
    'return errors.Wrap(err, "failed to execute post actions after all the ceph managers started")',
    'logger.Warningf("FORK: post-mgr failed (%v), continuing", err)'
)
with open("pkg/operator/ceph/cluster/cluster.go", "w") as f:
    f.write(code)
print("Patched cluster.go")

# ============================================================
# Patch 3: health.go — prevent removal of external MONs
# ============================================================
with open("pkg/operator/ceph/cluster/mon/health.go") as f:
    code = f.read()

# Prevent removal of MON not in clusterInfo but in quorum
code = code.replace(
    'if inQuorum && len(quorumStatus.Quorum) > desiredMonCount {\n\t\t\t\tlog.NamespacedWarning(c.Namespace, logger, "mon %q not in source of truth but in quorum, removing", mon.Name)\n\t\t\t\tif err := c.removeMon(mon.Name); err != nil {',
    'if inQuorum && len(quorumStatus.Quorum) > desiredMonCount {\n\t\t\t\tlog.NamespacedWarning(c.Namespace, logger, "FORK: mon %q not in source of truth but in quorum, SKIPPING removal", mon.Name)\n\t\t\t\tif false && err != nil {'
)

# Prevent removal of external MON when out of quorum
code = code.replace(
    '} else if !inQuorum && inInfo {',
    '} else if !inQuorum && inInfo && false /* FORK: never remove external mons */ {'
)

with open("pkg/operator/ceph/cluster/mon/health.go", "w") as f:
    f.write(code)
print("Patched health.go")

# ============================================================
# Patch 4: cr_manager.go — increase CacheSyncTimeout from 2m to 10m
# With 25+ CRD informers all syncing concurrently, 2m is too tight.
# The API server responds in <1s but under load some informers
# don't sync before the default 2-minute deadline.
# ============================================================
with open("pkg/operator/ceph/cr_manager.go") as f:
    code = f.read()

# Add "time" import
code = code.replace(
    '\t"context"\n',
    '\t"context"\n\t"time"\n'
)

# Increase CacheSyncTimeout from 2m default to 10m
code = code.replace(
    'Controller: config.Controller{\n\t\t\tSkipNameValidation: &skipNameValidation,\n\t\t},',
    'Controller: config.Controller{\n\t\t\tSkipNameValidation: &skipNameValidation,\n\t\t\tCacheSyncTimeout:   10 * time.Minute, // FORK: 25+ informers need more time than 2m default\n\t\t},'
)

with open("pkg/operator/ceph/cr_manager.go", "w") as f:
    f.write(code)
print("Patched cr_manager.go — CacheSyncTimeout 10m")
