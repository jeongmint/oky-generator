# oky backend

Image-to-3D inference service. Tested target: **Windows 11 + RTX 4070 Ti (12GB VRAM) + CUDA 12.1**. macOS (Apple Silicon, MPS) is supported but not yet verified.

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

## Setup (macOS, Apple Silicon)

Untested on real hardware yet — expect it to be slower than the 4070 Ti box. Runs on the MPS GPU (unsupported ops fall back to CPU automatically).

```bash
# 1. Prereqs: Xcode command line tools (TripoSR builds torchmcubes from source) + uv
xcode-select --install
brew install uv

# 2. From this directory:
cd backend
uv venv --python 3.10
uv sync

# 3. TripoSR reference code:
cd ..
git clone https://github.com/VAST-AI-Research/TripoSR.git
cd TripoSR
../backend/.venv/bin/pip install -e .
cd ../backend
```

Sanity check:

```bash
.venv/bin/python generate.py --input ../samples/chyla.png --output ../out.glb
```

The log should print `device=mps`. If MPS still errors out, force CPU with `--device cpu`. `--mc-resolution 128` keeps runs light while testing.

Gotchas seen when actually running on an M-series Mac:

- TripoSR has no `setup.py`, so `pip install -e .` fails — run with `PYTHONPATH=../../TripoSR` instead.
- `torchmcubes` (TripoSR dep) must be built: `uv pip install scikit-build-core cmake ninja pybind11`, then `uv pip install --no-build-isolation git+https://github.com/tatsy/torchmcubes.git`.
- Pin `transformers==4.35.0`; newer versions rename the DINO weights and model loading fails.
- `torchmcubes` is CPU-only and TripoSR's fallback in `tsr/models/isosurface.py` only catches `AttributeError`. Widen it to `except (AttributeError, RuntimeError):` or mesh extraction fails with `vol must be a CPU tensor`.

## Multi-view (InstantMesh)

`multiview.py` has two modes:

- `zero123` — front image only. Zero123++ imagines 6 views, InstantMesh reconstructs. Easy, but the side/back are the model's guess.
- `sheet` — your own front/side/back drawings go straight to InstantMesh. Follows the design; quality depends on how close the drawings are to true orthographic views.

Setup (Windows, after the TripoSR steps above):

```powershell
cd ..
git clone https://github.com/TencentARC/InstantMesh.git
cd backend
.\.venv\Scripts\pip install diffusers==0.20.2 pytorch-lightning==2.1.2 PyMCubes accelerate git+https://github.com/NVlabs/nvdiffrast/
```

Run (InstantMesh has no installable package, so put it on `PYTHONPATH`):

```powershell
$env:PYTHONPATH = "..\InstantMesh"
.\.venv\Scripts\python multiview.py zero123 --front ..\front.png --output ..\out.glb
.\.venv\Scripts\python multiview.py sheet --sheet ..\samples\chyla.png --output ..\out.glb --save-views
```

`sheet` options:

- `--sheet` splits a horizontal front | side | back image automatically; or pass `--front/--side/--back` separately.
- `--side-azimuth 90` — if the result comes out mirrored front-to-back, try `270`.
- `--mirror-side` (default on) also feeds the flipped side view as the opposite side. Turn off for asymmetric characters.
- `--save-views` writes the framed input views next to the GLB, handy for checking the split/scale.

InstantMesh needs CUDA (nvdiffrast) — it does not run on macOS. The view split/framing does, so `--save-views` can be checked on a Mac before the reconstruction step errors out.

Weights (~3 GB for Zero123++ + InstantMesh) download into the HF cache on first run.


## Notes on this box (RTX 4070 Ti, 12GB)

- TripoSR fits comfortably (~6GB VRAM at `--mc-resolution 256`).
- `--mc-resolution 512` works but pushes ~10GB and ~5x the runtime; usually not worth it for the PoC.
- For multi-view (InstantMesh) we'll likely need `--mc-resolution` reductions and fp16 — left for the next phase.

## Why a separate env from Blender?

Blender ships its own Python (3.11). Bundling torch + rembg + TripoSR into Blender's interpreter is painful and version-fragile. The addon talks to this env over `subprocess`, which keeps both sides clean.
