bl_info = {
    "name": "oky generator",
    "author": "oky",
    "version": (0, 1, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > oky",
    "description": "Generate a 3D mesh from reference images via a local backend.",
    "category": "Add Mesh",
}

import bpy

from . import operators, panel


_classes = (
    operators.OKY_OT_Generate,
    panel.OKY_PG_Settings,
    panel.OKY_PT_MainPanel,
)


def register() -> None:
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.oky = bpy.props.PointerProperty(type=panel.OKY_PG_Settings)


def unregister() -> None:
    del bpy.types.Scene.oky
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
