import re

# ============================================================
# Patch 1: mon.go — gradual migration from cephadm MONs to Rook MONs
#
# Supports three modes depending on external vs desired MON count:
#   1. All MONs external (rookTarget==0): save config, skip pod management
#   2. Mixed (rookTarget>0): manage only Rook MON pods, preserve external MONs
#   3. No external MONs: original Rook behavior (startMons with full count)
#
# "External" = a MON in ClusterInfo that has no rook-ceph-mon-<name> Deployment.
# "Rook"     = a MON that DOES have a matching Deployment in the namespace.
# ============================================================
with open("pkg/operator/ceph/cluster/mon/mon.go") as f:
    code = f.read()

# Replace the targeting + startMons block with gradual migration logic.
# The old string is the UPSTREAM code (before any patching).
old = '''	log.NamespacedInfo(c.Namespace, logger, "targeting the mon count %d", c.spec.Mon.Count)

	// create the mons for a new cluster or ensure mons are running in an existing cluster
	return c.ClusterInfo, c.startMons(c.spec.Mon.Count)'''

new = '''	// FORK: Gradual migration — support mixed cephadm + Rook MON clusters.
	// Classify each known MON as "external" (no K8s Deployment) or "rook" (has Deployment).
	// Only call startMons() for the Rook portion; external MONs are left untouched.
	allMons := c.ClusterInfo.AllMonitors()
	desiredCount := c.spec.Mon.Count

	// List existing rook-ceph-mon Deployments to distinguish Rook MONs from external ones.
	monDeployments, listErr := c.context.Clientset.AppsV1().Deployments(c.Namespace).List(
		c.ClusterInfo.Context,
		metav1.ListOptions{LabelSelector: fmt.Sprintf("app=%s", AppName)},
	)
	if listErr != nil {
		return nil, errors.Wrap(listErr, "FORK: failed to list mon deployments")
	}
	deploymentNames := make(map[string]bool, len(monDeployments.Items))
	for i := range monDeployments.Items {
		deploymentNames[monDeployments.Items[i].Name] = true
	}

	// Partition monitors into external (cephadm) vs rook (has K8s Deployment).
	externalMons := make(map[string]*cephclient.MonInfo)
	rookMons := make(map[string]*cephclient.MonInfo)
	for id, mon := range allMons {
		deployName := fmt.Sprintf("%s-%s", AppName, id)
		if deploymentNames[deployName] {
			rookMons[id] = mon
		} else {
			externalMons[id] = mon
		}
	}
	externalCount := len(externalMons)
	rookCount := len(rookMons)
	log.NamespacedInfo(c.Namespace, logger,
		"FORK: MON census — desired=%d external(cephadm)=%d rook(k8s)=%d",
		desiredCount, externalCount, rookCount)

	// Calculate how many Rook MON pods we need to reach the desired total.
	rookTarget := desiredCount - externalCount
	if rookTarget < 0 {
		rookTarget = 0
	}

	if rookTarget == 0 {
		// All MONs are external — pure cephadm mode. Save config and skip pod management.
		log.NamespacedInfo(c.Namespace, logger,
			"FORK: external MONs satisfy desired count (%d/%d), skipping MON pod management",
			externalCount, desiredCount)
		if err := c.saveMonConfig(); err != nil {
			log.NamespacedWarning(c.Namespace, logger, "FORK: failed to save mon config: %v", err)
		}
		return c.ClusterInfo, nil
	}

	// Mixed mode: we need rookTarget Rook MON pods alongside externalCount cephadm MONs.
	log.NamespacedInfo(c.Namespace, logger,
		"FORK: targeting %d Rook MON pod(s) (plus %d external) to reach desired %d",
		rookTarget, externalCount, desiredCount)

	// Temporarily remove external MONs from ClusterInfo so startMons() only sees/manages
	// the Rook subset. This prevents Rook from trying to create Deployments for cephadm MONs.
	savedInternal := c.ClusterInfo.InternalMonitors
	savedExternal := c.ClusterInfo.ExternalMons
	rookOnly := make(map[string]*cephclient.MonInfo, len(rookMons))
	for id, mon := range rookMons {
		rookOnly[id] = mon
	}
	c.ClusterInfo.InternalMonitors = rookOnly
	c.ClusterInfo.ExternalMons = nil

	startErr := c.startMons(rookTarget)

	// Restore the full monitor set (rook + external) regardless of error.
	c.ClusterInfo.InternalMonitors = savedInternal
	c.ClusterInfo.ExternalMons = savedExternal

	if startErr != nil {
		return c.ClusterInfo, errors.Wrap(startErr, "FORK: failed to start rook mon pods")
	}

	// Merge any newly-created Rook MONs back into InternalMonitors.
	// startMons() may have added entries to the rookOnly map during provisioning.
	for id, mon := range rookOnly {
		if _, exists := c.ClusterInfo.InternalMonitors[id]; !exists {
			c.ClusterInfo.InternalMonitors[id] = mon
		}
	}

	// Save the combined config (external + rook MONs).
	if err := c.saveMonConfig(); err != nil {
		return c.ClusterInfo, errors.Wrap(err, "FORK: failed to save combined mon config")
	}

	log.NamespacedInfo(c.Namespace, logger,
		"FORK: MON start complete — %d total (%d rook + %d external)",
		len(c.ClusterInfo.AllMonitors()), rookTarget, externalCount)
	return c.ClusterInfo, nil'''

assert old in code, "FATAL: Patch 1 target block not found in mon.go — upstream source changed?"
code = code.replace(old, new)
with open("pkg/operator/ceph/cluster/mon/mon.go", "w") as f:
    f.write(code)
print("Patched mon.go — gradual MON migration (external + rook coexistence)")

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
