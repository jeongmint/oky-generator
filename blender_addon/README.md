# oky Blender addon

Blender 4.x sidebar addon. Sends a reference image to the local backend and imports the result.

## Install

Two options.

### A. Zip & install (normal users)

1. Zip this folder so the archive contains a top-level `blender_addon/` directory with `__init__.py` inside.
2. Blender → `Edit > Preferences > Add-ons > Install...` → pick the zip.
3. Enable **oky generator**.

### B. Symlink (development)

Point Blender at this folder directly so edits land without re-zipping.

**macOS:**

```bash
ln -s "$PWD/blender_addon" \
  "$HOME/Library/Application Support/Blender/4.x/scripts/addons/oky_generator"
```

**Windows (PowerShell, admin):**

```powershell
New-Item -ItemType SymbolicLink `
  -Path "$env:APPDATA\Blender Foundation\Blender\4.x\scripts\addons\oky_generator" `
  -Target "$PWD\blender_addon"
```

Replace `4.x` with your Blender version.

## Usage

1. Open the sidebar in the 3D viewport (`N` key) → **oky** tab.
2. **Reference images** → set Front (Side/Back are placeholders for the multi-view phase).
3. **Backend** → point to the backend's Python interpreter and `generate.py`:
   - Python: `…/backend/.venv/Scripts/python.exe` (Windows) or `…/backend/.venv/bin/python` (Linux/mac CPU test).
   - Script: `…/backend/generate.py`.
4. Hit **Generate 3D**. The GLB lands in `Output dir` (default: `//oky_out` next to the .blend file) and gets imported into the scene.

## Troubleshooting

- *"Backend failed"* — Blender only shows the last few lines. Re-run the same command in a terminal to see the full trace.
- Generation freezes Blender's UI: that's expected for the PoC (synchronous subprocess). A modal/timer-based version is on the roadmap.
