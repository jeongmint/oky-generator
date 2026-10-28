import bpy
from bpy.props import BoolProperty, IntProperty, PointerProperty, StringProperty
from bpy.types import Panel, PropertyGroup


class OKY_PG_Settings(PropertyGroup):
    front_image: StringProperty(
        name="Front",
        subtype="FILE_PATH",
        description="Front-view reference image",
    )
    side_image: StringProperty(
        name="Side",
        subtype="FILE_PATH",
        description="Side-view reference image (optional, used once multi-view is wired up)",
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
        description="Path to backend/generate.py",
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


class OKY_PT_MainPanel(Panel):
    bl_label = "oky generator"
    bl_idname = "OKY_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "oky"

    def draw(self, context):
        layout = self.layout
        s = context.scene.oky

        col = layout.column(align=True)
        col.label(text="Reference images")
        col.prop(s, "front_image")
        col.prop(s, "side_image")
        col.prop(s, "back_image")

        col = layout.column(align=True)
        col.label(text="Backend")
        col.prop(s, "backend_python")
        col.prop(s, "backend_script")
        col.prop(s, "output_dir")

        col = layout.column(align=True)
        col.label(text="Options")
        col.prop(s, "remove_bg")
        col.prop(s, "mc_resolution")

        layout.separator()
        layout.operator("oky.generate", icon="MESH_MONKEY")
