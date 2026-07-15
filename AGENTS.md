# rook-ceph-fork — local agent notes only

Doctrine and fleet delivery law live in the **host always-on constitution**
(`~/.grok/AGENTS.md` / Doctrine template). This file must **not** restate,
weaken, or fork that law (including PR-vs-direct-trunk delivery).

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
