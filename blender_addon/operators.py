import shlex
import subprocess
import time
from pathlib import Path

import bpy
from bpy.types import Operator


class OKY_OT_Generate(Operator):
    bl_idname = "oky.generate"
    bl_label = "Generate 3D"
    bl_description = "Run the backend on the front image and import the resulting GLB"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        s = context.scene.oky

        front = bpy.path.abspath(s.front_image) if s.front_image else ""
        python = bpy.path.abspath(s.backend_python) if s.backend_python else ""
        script = bpy.path.abspath(s.backend_script) if s.backend_script else ""
        out_dir = Path(bpy.path.abspath(s.output_dir or "//oky_out"))

        if not front or not Path(front).is_file():
            self.report({"ERROR"}, "Front image is required")
            return {"CANCELLED"}
        if not python or not Path(python).is_file():
            self.report({"ERROR"}, "Backend Python interpreter not set")
            return {"CANCELLED"}
        if not script or not Path(script).is_file():
            self.report({"ERROR"}, "Backend script (generate.py) not set")
            return {"CANCELLED"}

        out_dir.mkdir(parents=True, exist_ok=True)
        out_glb = out_dir / f"oky_{int(time.time())}.glb"

        cmd = [
            python,
            script,
            "--input", front,
            "--output", str(out_glb),
            "--mc-resolution", str(s.mc_resolution),
        ]
        if not s.remove_bg:
            cmd.append("--no-remove-bg")

        self.report({"INFO"}, "oky: " + " ".join(shlex.quote(c) for c in cmd))

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
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
