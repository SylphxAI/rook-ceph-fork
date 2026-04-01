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
# Patch 4: cr_manager.go — disable unused controllers
# Each Rook controller uses controller.New() which defaults to
# a 2-minute CacheSyncTimeout. With 21 informers starting
# concurrently, some fail to sync in time. The manager-level
# config.Controller.CacheSyncTimeout does NOT propagate to
# controllers created via controller.New() (only builder pattern).
# Fix: remove controllers for CRDs we don't use, reducing
# informer count from 21 to 10.
# ============================================================
with open("pkg/operator/ceph/cr_manager.go") as f:
    code = f.read()

# Replace AddToManagerFuncs slice — keep only what we need
old_slice = '''var AddToManagerFuncs = []func(manager.Manager, *clusterd.Context, context.Context, opcontroller.OperatorConfig) error{
	nodedaemon.Add,
	pool.Add,
	objectuser.Add,
	realm.Add,
	zonegroup.Add,
	zone.Add,
	object.Add,
	file.Add,
	nfs.Add,
	rbd.Add,
	client.Add,
	nvmeof.Add,
	mirror.Add,
	Add,
	csi.Add,
	bucket.Add,
	topic.Add,
	notification.Add,
	subvolumegroup.Add,
	radosnamespace.Add,
	cosi.Add,
}'''

new_slice = '''// FORK: Reduced controller set — only controllers for CRDs we actually use.
// Removes 11 unused controllers (realm, zonegroup, zone, nfs, rbd, client,
// nvmeof, mirror, topic, notification, cosi) to eliminate cache sync timeouts.
// Each controller starts an informer; 21 concurrent informers exceeded the
// 2-minute per-controller CacheSyncTimeout on startup.
var AddToManagerFuncs = []func(manager.Manager, *clusterd.Context, context.Context, opcontroller.OperatorConfig) error{
	nodedaemon.Add,
	pool.Add,
	objectuser.Add,
	object.Add,
	file.Add,
	Add,
	csi.Add,
	bucket.Add,
	subvolumegroup.Add,
	radosnamespace.Add,
}

// FORK: Keep removed imports referenced to avoid Go compile errors.
var (
	_ = realm.Add
	_ = zonegroup.Add
	_ = zone.Add
	_ = nfs.Add
	_ = rbd.Add
	_ = client.Add
	_ = nvmeof.Add
	_ = mirror.Add
	_ = topic.Add
	_ = notification.Add
	_ = cosi.Add
)'''

assert old_slice in code, "FATAL: AddToManagerFuncs slice not found — source changed?"
code = code.replace(old_slice, new_slice)

with open("pkg/operator/ceph/cr_manager.go", "w") as f:
    f.write(code)
print("Patched cr_manager.go — reduced controllers from 21 to 10")
