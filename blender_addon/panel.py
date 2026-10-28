import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty
from bpy.types import Panel, PropertyGroup


class OKY_PG_Settings(PropertyGroup):
    mode: EnumProperty(
        name="Mode",
        items=(
            ("TRIPOSR", "Single image (TripoSR)", "Front image -> GLB. Fast, low detail"),
            ("ZERO123", "Multi-view: imagined (InstantMesh)", "Front image -> Zero123++ imagines 6 views -> InstantMesh"),
            ("SHEET", "Multi-view: own sheet (InstantMesh)", "Your front/side/back drawings -> InstantMesh"),
        ),
        default="TRIPOSR",
    )
    use_sheet: BoolProperty(
        name="Single turnaround sheet",
        default=False,
        description="One image with front | side | back left to right, split automatically",
    )
    sheet_image: StringProperty(
        name="Sheet",
        subtype="FILE_PATH",
        description="Turnaround sheet (front | side | back)",
    )
    front_image: StringProperty(
        name="Front",
        subtype="FILE_PATH",
        description="Front-view reference image",
    )
    side_image: StringProperty(
        name="Side",
        subtype="FILE_PATH",
        description="Side-view reference image",
    )
    back_image: StringProperty(
        name="Back",
        subtype="FILE_PATH",
        description="Back-view reference image (optional)",
    )
    backend_python: StringProperty(
        name="Python",
        subtype="FILE_PATH",
        description="Path to the Python interpreter for the backend env (e.g. .venv/Scripts/python.exe)",
    )
    backend_script: StringProperty(
        name="Script",
        subtype="FILE_PATH",
        description="Path to backend/generate.py (multiview.py is picked up from the same folder)",
    )
    instantmesh_dir: StringProperty(
        name="InstantMesh",
        subtype="DIR_PATH",
        description="Path to the cloned InstantMesh repo (added to PYTHONPATH for multi-view modes)",
    )
    output_dir: StringProperty(
        name="Output dir",
        subtype="DIR_PATH",
        default="//oky_out",
    )
    remove_bg: BoolProperty(name="Remove background", default=True)
    mc_resolution: IntProperty(
        name="MC resolution",
        default=256,
        min=64,
        max=512,
        description="Marching cubes resolution. Higher = more polys, slower.",
    )
    side_azimuth: FloatProperty(
        name="Side azimuth",
        default=90.0,
        min=0.0,
        max=360.0,
        description="Camera angle of the side view. Try 270 if the mesh comes out mirrored",
    )
    mirror_side: BoolProperty(
        name="Mirror side",
        default=True,
        description="Also use the flipped side view as the opposite side (symmetric characters)",
    )
    diffusion_steps: IntProperty(name="Diffusion steps", default=75, min=10, max=200)


class OKY_PT_MainPanel(Panel):
    bl_label = "oky generator"
    bl_idname = "OKY_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "oky"

    def draw(self, context):
        layout = self.layout
        s = context.scene.oky

        layout.prop(s, "mode", text="")

        col = layout.column(align=True)
        col.label(text="Reference images")
        if s.mode == "SHEET":
            col.prop(s, "use_sheet")
            if s.use_sheet:
                col.prop(s, "sheet_image")
            else:
                col.prop(s, "front_image")
                col.prop(s, "side_image")
                col.prop(s, "back_image")
        else:
            col.prop(s, "front_image")

        col = layout.column(align=True)
        col.label(text="Backend")
        col.prop(s, "backend_python")
        col.prop(s, "backend_script")
        if s.mode != "TRIPOSR":
            col.prop(s, "instantmesh_dir")
        col.prop(s, "output_dir")

        col = layout.column(align=True)
        col.label(text="Options")
        if s.mode == "TRIPOSR":
            col.prop(s, "remove_bg")
            col.prop(s, "mc_resolution")
        elif s.mode == "ZERO123":
            col.prop(s, "diffusion_steps")
        else:
            col.prop(s, "side_azimuth")
            col.prop(s, "mirror_side")

        layout.separator()
        layout.operator("oky.generate", icon="MESH_MONKEY")
