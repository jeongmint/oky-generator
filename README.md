# oky-generator

Reference image(s) → 3D mesh, as a Blender addon backed by a local Python service.

PoC stage: single front image → low-poly GLB via TripoSR. Multi-view (front/side/back) and high-poly post-processing land later.

## Layout

- `backend/` — Python CLI that runs the image-to-3D model. Runs on the **Windows + RTX 4070 Ti** box.
- `blender_addon/` — Blender 4.x addon. Lightweight UI that shells out to the backend and imports the resulting GLB. Runs anywhere Blender runs (incl. macOS).

## Quick start

1. On the Windows machine, set up `backend/` — see `backend/README.md`.
2. Install the Blender addon — see `blender_addon/README.md`.
3. In Blender's `View3D > Sidebar > oky` panel, point to the backend interpreter + script, pick a front image, hit **Generate 3D**.

## Roadmap

- [x] Single front image → GLB (TripoSR)
- [x] Multi-view (front/side/back) via InstantMesh — implemented, not yet verified on the CUDA box
- [ ] High-poly post-processing (Subdivision + Multires + displacement bake)
- [ ] Persistent backend daemon (avoid model reload per request)
