# oky backend

Image-to-3D inference service. Tested target: **Windows 11 + RTX 4070 Ti (12GB VRAM) + CUDA 12.1**.

## Setup (Windows, one-time)

```powershell
# 1. Install uv (https://docs.astral.sh/uv/) if you don't have it
winget install --id=astral-sh.uv -e

# 2. From this directory:
cd backend
uv venv --python 3.10
uv sync

# 3. TripoSR's reference code lives outside PyPI — clone it next to this folder:
cd ..
git clone https://github.com/VAST-AI-Research/TripoSR.git
cd TripoSR
..\backend\.venv\Scripts\pip install -e .
cd ..\backend
```

Sanity check:

```powershell
.\.venv\Scripts\python generate.py --input ..\sample.png --output ..\out.glb
```

First run downloads the TripoSR weights (~1.5 GB) into the HF cache.

## Notes on this box (RTX 4070 Ti, 12GB)

- TripoSR fits comfortably (~6GB VRAM at `--mc-resolution 256`).
- `--mc-resolution 512` works but pushes ~10GB and ~5x the runtime; usually not worth it for the PoC.
- For multi-view (InstantMesh) we'll likely need `--mc-resolution` reductions and fp16 — left for the next phase.

## Why a separate env from Blender?

Blender ships its own Python (3.11). Bundling torch + rembg + TripoSR into Blender's interpreter is painful and version-fragile. The addon talks to this env over `subprocess`, which keeps both sides clean.
