# ============================================================
# Single patch: increase CacheSyncTimeout from 2m to 10m
#
# Root cause: clusters with many Secrets (1400+) and CRDs (200+)
# cause the shared informer cache to take >2m to sync on startup.
# This is not a Rook bug — it's a resource-budget issue at scale.
#
# controller-runtime's DefaultFromConfig propagates CacheSyncTimeout
# from manager.Options.Controller to all controllers created via
# controller.New(), even without the builder pattern.
# ============================================================
import re

with open("pkg/operator/ceph/cr_manager.go") as f:
    code = f.read()

# Add "time" import
code = code.replace(
    '\t"context"\n',
    '\t"context"\n\t"time"\n'
)

# Set CacheSyncTimeout to 10 minutes
old = '''Controller: config.Controller{
			SkipNameValidation: &skipNameValidation,
		},'''

new = '''Controller: config.Controller{
			SkipNameValidation: &skipNameValidation,
			CacheSyncTimeout:   10 * time.Minute,
		},'''

assert old in code, "FATAL: manager options not found in cr_manager.go"
code = code.replace(old, new)

with open("pkg/operator/ceph/cr_manager.go", "w") as f:
    f.write(code)
print("Patched cr_manager.go — CacheSyncTimeout 10m (1 patch, no controller changes)")
