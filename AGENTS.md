# Rook Ceph Fork Agent Instructions

## Scope

This file is the repo-local operating policy for agents working in
`SylphxAI/rook-ceph-fork`. Organization-wide engineering doctrine is owned by
`SylphxAI/doctrine`; `PROJECT.md` and `.doctrine/project.json` own this
repository's local identity, lifecycle, boundary, and delivery facts.

This repository owns a small forked Rook/Ceph container build that applies local
patches to upstream Rook and publishes a GHCR image.

## Read First

1. `PROJECT.md` and `.doctrine/project.json` for project goals, boundaries, and
   delivery proof.
2. `Dockerfile` for the upstream Rook version, build target, image base, and
   published tag.
3. `patch.py` before changing fork behavior.
4. `.github/workflows/build.yml` before changing image build or push behavior.

## Non-Negotiables

- Keep fork behavior minimal, explicit, and auditable. Every patch must be
  visible in `patch.py` or a documented equivalent.
- Do not push GHCR images from pull requests or non-main branches.
- Do not silently change the upstream Rook version, image tag, or patch purpose.
- Runtime use of the image requires cluster rollout/readback evidence outside
  this repo.

## Validation

Use the narrowest meaningful validation first, then broaden as needed:

- `python3 -m py_compile patch.py`
- Docker build for the forked image
- GitHub Actions build proof
- GHCR image digest readback for main-branch image publication

Docs-only boundary changes may be validated by diff review, referenced-file
checks, and the central project manifest audit.
