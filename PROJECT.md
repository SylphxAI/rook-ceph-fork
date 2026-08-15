# Rook Ceph Fork Project

Rook Ceph Fork builds a patched Rook/Ceph container image. The current patch
increases Rook manager cache sync timeout for large clusters and publishes the
forked image to GHCR for controlled infrastructure use.

## Lifecycle

- Lifecycle: `active`
- Layer: `integration`

## Goals

- Maintain a minimal, auditable patch set on top of a specific upstream Rook
  version.
- Build the patched Rook binary into a container image.
- Publish GHCR image artifacts from `main` with digest/readback evidence.

## Non-Goals

- Do not become the upstream Rook source of truth.
- Do not own cluster rollout policy, Ceph operations, or Kubernetes runtime
  configuration outside this image artifact.
- Do not push release images from pull requests or non-main branches.

## Boundaries

This repository owns `Dockerfile`, `patch.py`, and the GHCR image build workflow.
It does not own upstream Rook, production cluster manifests, Ceph runtime policy,
or incident recovery outside the image artifact handoff.

## Delivery

Pull requests should build the image without pushing. Main branch pushes may
publish `ghcr.io/sylphxai/rook-ceph-fork:v1.19.3-mon-bypass`. Production proof
for image publication requires GitHub Actions build success and GHCR digest
readback; runtime adoption additionally requires cluster rollout/readback proof.
