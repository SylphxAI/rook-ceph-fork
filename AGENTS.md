# rook-ceph-fork — local agent notes only

Static engineering and delivery standards load from the active Skills runtime
([SylphxAI/skills](https://github.com/SylphxAI/skills) is binding instruction
SSOT). Doctrine and Mission Control are retired historical lineage and must not
be loaded as current instruction authority.

Local truth: `PROJECT.md`, `.doctrine/project.json` when present.

## Boundary hazards

- Keep fork behavior minimal, explicit, and auditable. Every patch must be
- Do not silently change the upstream Rook version, image tag, or patch purpose.
- Runtime use of the image requires cluster rollout/readback evidence outside

## Local commands

- `python3 -m py_compile patch.py`
- Docker build for the forked image
- GitHub Actions build proof
- GHCR image digest readback for main-branch image publication
- Prefer the **narrowest** affected check before full workspace runs.
- Report layers honestly: local diff · trunk FF · deploy · prod proof (do not collapse).

## Validation notes

- Prefer the **narrowest** affected check before full workspace runs.
- Report layers honestly: local diff · trunk FF · deploy · prod proof (do not collapse).
