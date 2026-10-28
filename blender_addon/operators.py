import os
import shlex
import subprocess
import time
from pathlib import Path

import bpy
from bpy.types import Operator


def _path(value: str) -> str:
    return bpy.path.abspath(value) if value else ""


def _is_file(value: str) -> bool:
    return bool(value) and Path(value).is_file()


class OKY_OT_Generate(Operator):
    bl_idname = "oky.generate"
    bl_label = "Generate 3D"
    bl_description = "Run the backend on the reference image(s) and import the resulting GLB"
    bl_options = {"REGISTER", "UNDO"}

    def _build_command(self, s, python: str, script: str, out_glb: Path):
        """Return (cmd, error)."""
        front = _path(s.front_image)

        if s.mode == "TRIPOSR":
            if not _is_file(front):
                return None, "Front image is required"
            cmd = [
                python,
                script,
                "--input", front,
                "--output", str(out_glb),
                "--mc-resolution", str(s.mc_resolution),
            ]
            if not s.remove_bg:
                cmd.append("--no-remove-bg")
            return cmd, None

        multiview = str(Path(script).with_name("multiview.py"))
        if not _is_file(multiview):
            return None, f"{multiview} not found next to the backend script"

        if s.mode == "ZERO123":
            if not _is_file(front):
                return None, "Front image is required"
            return [
                python, multiview, "zero123",
                "--front", front,
                "--output", str(out_glb),
                "--steps", str(s.diffusion_steps),
            ], None

        cmd = [python, multiview, "sheet", "--output", str(out_glb)]
        if s.use_sheet:
            sheet = _path(s.sheet_image)
            if not _is_file(sheet):
                return None, "Sheet image is required"
            cmd += ["--sheet", sheet]
        else:
            side, back = _path(s.side_image), _path(s.back_image)
            if not _is_file(front) or not _is_file(side):
                return None, "Front and Side images are required"
            cmd += ["--front", front, "--side", side]
            if _is_file(back):
                cmd += ["--back", back]
        cmd += ["--side-azimuth", str(s.side_azimuth)]
        cmd.append("--mirror-side" if s.mirror_side else "--no-mirror-side")
        return cmd, None

    def execute(self, context):
        s = context.scene.oky

        python = _path(s.backend_python)
        script = _path(s.backend_script)
        out_dir = Path(bpy.path.abspath(s.output_dir or "//oky_out"))

        if not _is_file(python):
            self.report({"ERROR"}, "Backend Python interpreter not set")
            return {"CANCELLED"}
        if not _is_file(script):
            self.report({"ERROR"}, "Backend script (generate.py) not set")
            return {"CANCELLED"}

        out_dir.mkdir(parents=True, exist_ok=True)
        out_glb = out_dir / f"oky_{int(time.time())}.glb"

        cmd, error = self._build_command(s, python, script, out_glb)
        if error:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}

        env = os.environ.copy()
        if s.mode != "TRIPOSR":
            instantmesh = _path(s.instantmesh_dir)
            if not instantmesh or not Path(instantmesh).is_dir():
                self.report({"ERROR"}, "InstantMesh repo folder not set")
                return {"CANCELLED"}
            env["PYTHONPATH"] = os.pathsep.join(p for p in (instantmesh, env.get("PYTHONPATH")) if p)

        self.report({"INFO"}, "oky: " + " ".join(shlex.quote(c) for c in cmd))

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                env=env,
                # InstantMesh resolves its configs relative to the repo.
                cwd=_path(s.instantmesh_dir) if s.mode != "TRIPOSR" else None,
            )
        except OSError as exc:
            self.report({"ERROR"}, f"Failed to launch backend: {exc}")
            return {"CANCELLED"}

        if result.returncode != 0:
            tail = (result.stderr or result.stdout or "").strip().splitlines()[-5:]
            self.report({"ERROR"}, "Backend failed: " + " | ".join(tail))
            return {"CANCELLED"}

        if not out_glb.is_file():
            self.report({"ERROR"}, f"Backend completed but {out_glb} not found")
            return {"CANCELLED"}

        bpy.ops.import_scene.gltf(filepath=str(out_glb))
        self.report({"INFO"}, f"oky: imported {out_glb.name}")
        return {"FINISHED"}
