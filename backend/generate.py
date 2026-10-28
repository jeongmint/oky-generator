"""Single-image to 3D GLB generation via TripoSR.

Usage:
    python generate.py --input front.png --output out.glb
    python generate.py --input front.png --output out.glb --no-remove-bg
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
import typer
from PIL import Image

app = typer.Typer(add_completion=False)


def _pick_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _preprocess(image_path: Path, remove_bg: bool, foreground_ratio: float) -> Image.Image:
    image = Image.open(image_path).convert("RGBA")

    if remove_bg:
        from rembg import remove

        image = remove(image)

    rgba = np.array(image).astype(np.float32) / 255.0
    rgb = rgba[..., :3]
    alpha = rgba[..., 3:4]
    # Composite onto neutral grey, which TripoSR was trained against.
    composited = rgb * alpha + (1.0 - alpha) * 0.5
    image = Image.fromarray((composited * 255).astype(np.uint8))

    # Center-crop to the foreground bounding box, then pad to a square.
    bbox = Image.fromarray((alpha[..., 0] * 255).astype(np.uint8)).getbbox()
    if bbox is not None:
        image = image.crop(bbox)

    side = int(max(image.size) / foreground_ratio)
    canvas = Image.new("RGB", (side, side), (127, 127, 127))
    canvas.paste(image, ((side - image.size[0]) // 2, (side - image.size[1]) // 2))
    return canvas.resize((512, 512), Image.LANCZOS)


@app.command()
def main(
    input: Path = typer.Option(..., "--input", "-i", exists=True, help="Input image path"),
    output: Path = typer.Option(..., "--output", "-o", help="Output GLB path"),
    remove_bg: bool = typer.Option(True, "--remove-bg/--no-remove-bg"),
    foreground_ratio: float = typer.Option(0.85),
    mc_resolution: int = typer.Option(256, help="Marching cubes resolution (128/256/512)"),
    model_name: str = typer.Option("stabilityai/TripoSR"),
) -> None:
    device = _pick_device()
    typer.echo(f"[oky] device={device}")

    # Lazy import — heavy and only needed at runtime.
    from tsr.system import TSR

    typer.echo(f"[oky] loading {model_name} ...")
    model = TSR.from_pretrained(
        model_name,
        config_name="config.yaml",
        weight_name="model.ckpt",
    )
    model.renderer.set_chunk_size(8192)
    model.to(device)

    typer.echo(f"[oky] preprocessing {input} ...")
    image = _preprocess(input, remove_bg=remove_bg, foreground_ratio=foreground_ratio)

    typer.echo("[oky] running inference ...")
    with torch.no_grad():
        scene_codes = model([image], device=device)

    typer.echo(f"[oky] extracting mesh @ resolution={mc_resolution} ...")
    meshes = model.extract_mesh(scene_codes, has_vertex_color=True, resolution=mc_resolution)

    output.parent.mkdir(parents=True, exist_ok=True)
    meshes[0].export(output.as_posix())
    typer.echo(f"[oky] wrote {output} ({len(meshes[0].faces)} faces)")


if __name__ == "__main__":
    app()
