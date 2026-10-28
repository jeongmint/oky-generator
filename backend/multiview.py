"""Multi-view to 3D GLB generation via InstantMesh.

Two modes:
    zero123  Single front image -> Zero123++ imagines 6 views -> InstantMesh.
    sheet    Your own front/side/back drawings are fed straight to InstantMesh
             (no imagined views, so the result follows the design).

Usage:
    python multiview.py zero123 --front front.png --output out.glb
    python multiview.py sheet --front f.png --side s.png --back b.png --output out.glb
    python multiview.py sheet --sheet turnaround.png --output out.glb   # auto-split front|side|back

Requires the InstantMesh repo on PYTHONPATH (see README) and a CUDA GPU.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import typer
from PIL import Image

app = typer.Typer(add_completion=False)

VIEW_RES = 320
FOREGROUND_RATIO = 0.85


def _instantmesh_root() -> Path:
    import src  # InstantMesh's top-level package

    return Path(src.__file__).resolve().parent.parent


def _load_reconstructor(config_path: Path, device: torch.device):
    from huggingface_hub import hf_hub_download
    from omegaconf import OmegaConf
    from src.utils.train_util import instantiate_from_config

    config = OmegaConf.load(config_path)
    config_name = config_path.stem

    model = instantiate_from_config(config.model_config)
    ckpt = hf_hub_download(
        repo_id="TencentARC/InstantMesh",
        filename=f"{config_name.replace('-', '_')}.ckpt",
        repo_type="model",
    )
    state_dict = torch.load(ckpt, map_location="cpu")["state_dict"]
    state_dict = {k[14:]: v for k, v in state_dict.items() if k.startswith("lrm_generator.")}
    model.load_state_dict(state_dict, strict=True)
    model = model.to(device)
    model.init_flexicubes_geometry(device, fovy=30.0)
    return model.eval(), config.infer_config


def _cameras(azimuths, elevations, radius: float, fov: float = 30.0) -> torch.Tensor:
    """Same layout as InstantMesh's get_zero123plus_input_cameras, but for arbitrary poses."""
    from src.utils.camera_util import FOV_to_intrinsics, spherical_camera_pose

    n = len(azimuths)
    c2ws = spherical_camera_pose(
        np.asarray(azimuths, dtype=float), np.asarray(elevations, dtype=float), radius
    ).float().flatten(-2)
    Ks = FOV_to_intrinsics(fov).unsqueeze(0).repeat(n, 1, 1).float().flatten(-2)
    intrinsics = torch.stack([Ks[:, 0], Ks[:, 4], Ks[:, 2], Ks[:, 5]], dim=-1)
    return torch.cat([c2ws[:, :12], intrinsics], dim=-1).unsqueeze(0)


def _to_rgba(image: Image.Image, session) -> Image.Image:
    from rembg import remove

    image = image.convert("RGBA")
    if image.getextrema()[3][0] == 255:  # no transparency yet
        rgb = image.convert("RGB")
        image = remove(image, session=session)
        # rembg turns pale flat fills (belly, horns) semi-transparent on drawings.
        # Make everything inside the silhouette opaque and keep the original colors.
        from PIL import ImageDraw

        mask = image.getchannel("A").point(lambda a: 255 if a > 16 else 0)
        mask = Image.eval(mask, lambda a: 255 - a).copy()  # background = 255
        padded = Image.new("L", (mask.width + 2, mask.height + 2), 255)
        padded.paste(mask, (1, 1))
        ImageDraw.floodfill(padded, (0, 0), 128)  # mark background reachable from outside
        inside = padded.crop((1, 1, mask.width + 1, mask.height + 1)).point(lambda a: 0 if a == 128 else 255)
        image = rgb.copy()
        image.putalpha(inside)
    return image


def _split_sheet(sheet: Image.Image, session) -> list[Image.Image]:
    """Split a horizontal turnaround sheet into its views using empty alpha columns."""
    rgba = _to_rgba(sheet, session)
    filled = np.array(rgba)[..., 3].max(axis=0) > 16
    spans, start = [], None
    for x, f in enumerate(filled):
        if f and start is None:
            start = x
        elif not f and start is not None:
            spans.append((start, x))
            start = None
    if start is not None:
        spans.append((start, len(filled)))
    # Drop specks, keep the three widest regions in left-to-right order.
    spans = sorted(sorted(spans, key=lambda s: s[1] - s[0])[-3:])
    if len(spans) != 3:
        raise typer.BadParameter(f"expected 3 views in the sheet, found {len(spans)}")
    return [rgba.crop((a, 0, b, rgba.height)) for a, b in spans]


def _frame_views(views: list[Image.Image]) -> list[Image.Image]:
    """Crop each view to its foreground and place all of them at one shared scale,
    composited on white (what InstantMesh's reconstructor expects)."""
    crops = []
    for v in views:
        bbox = v.getchannel("A").point(lambda a: 255 if a > 16 else 0).getbbox()
        crops.append(v.crop(bbox) if bbox else v)
    # One scale for every view, so the character is the same size from each side.
    scale = VIEW_RES * FOREGROUND_RATIO / max(max(c.size) for c in crops)
    framed = []
    for c in crops:
        w, h = max(1, round(c.width * scale)), max(1, round(c.height * scale))
        c = c.resize((w, h), Image.LANCZOS)
        canvas = Image.new("RGBA", (VIEW_RES, VIEW_RES), (255, 255, 255, 255))
        canvas.alpha_composite(c, ((VIEW_RES - w) // 2, (VIEW_RES - h) // 2))
        framed.append(canvas.convert("RGB"))
    return framed


def _stack(images: list[Image.Image]) -> torch.Tensor:
    arr = np.stack([np.asarray(i, dtype=np.float32) / 255.0 for i in images])
    return torch.from_numpy(arr).permute(0, 3, 1, 2).contiguous().unsqueeze(0)  # (1, N, 3, H, W)


def _zero123_views(front: Path, steps: int, seed: int, session, device) -> list[Image.Image]:
    from diffusers import DiffusionPipeline, EulerAncestralDiscreteScheduler
    from huggingface_hub import hf_hub_download
    from src.utils.infer_util import resize_foreground

    pipeline = DiffusionPipeline.from_pretrained(
        "sudo-ai/zero123plus-v1.2",
        custom_pipeline=str(_instantmesh_root() / "zero123plus"),
        torch_dtype=torch.float16,
    )
    pipeline.scheduler = EulerAncestralDiscreteScheduler.from_config(
        pipeline.scheduler.config, timestep_spacing="trailing"
    )
    unet = hf_hub_download(
        repo_id="TencentARC/InstantMesh", filename="diffusion_pytorch_model.bin", repo_type="model"
    )
    pipeline.unet.load_state_dict(torch.load(unet, map_location="cpu"), strict=True)
    pipeline = pipeline.to(device)

    image = resize_foreground(_to_rgba(Image.open(front), session), FOREGROUND_RATIO)
    grid = pipeline(
        image,
        num_inference_steps=steps,
        generator=torch.Generator(device=device).manual_seed(seed),
    ).images[0]
    del pipeline
    torch.cuda.empty_cache()

    # 960x640 grid -> 6 tiles of 320x320, row-major (az 30, 90, 150, 210, 270, 330).
    return [
        grid.crop((c * VIEW_RES, r * VIEW_RES, (c + 1) * VIEW_RES, (r + 1) * VIEW_RES))
        for r in range(3)
        for c in range(2)
    ]


def _reconstruct(model, infer_config, images: torch.Tensor, cameras: torch.Tensor, output: Path) -> int:
    from src.utils.mesh_util import save_glb

    with torch.no_grad():
        planes = model.forward_planes(images, cameras)
        vertices, faces, colors = model.extract_mesh(planes, use_texture_map=False, **infer_config)
    output.parent.mkdir(parents=True, exist_ok=True)
    save_glb(vertices, faces, colors, output.as_posix())
    return len(faces)


def _setup(config: Optional[Path]):
    if not torch.cuda.is_available():
        typer.echo("[oky] InstantMesh needs a CUDA GPU (nvdiffrast).", err=True)
        raise typer.Exit(1)
    device = torch.device("cuda")
    config = config or _instantmesh_root() / "configs" / "instant-mesh-large.yaml"
    typer.echo(f"[oky] loading InstantMesh ({config.stem}) ...")
    return device, *_load_reconstructor(config, device)


@app.command()
def zero123(
    front: Path = typer.Option(..., exists=True, help="Front image"),
    output: Path = typer.Option(..., "--output", "-o", help="Output GLB path"),
    steps: int = typer.Option(75, help="Zero123++ denoising steps"),
    seed: int = typer.Option(42),
    config: Optional[Path] = typer.Option(None, help="InstantMesh config yaml (default: instant-mesh-large)"),
    save_views: bool = typer.Option(False, help="Also save the imagined views next to the GLB"),
) -> None:
    """Front image -> Zero123++ imagines 6 views -> InstantMesh."""
    from rembg import new_session

    device, model, infer_config = _setup(config)
    typer.echo("[oky] imagining views with Zero123++ ...")
    views = _zero123_views(front, steps, seed, new_session(), device)
    if save_views:
        output.parent.mkdir(parents=True, exist_ok=True)
        for i, v in enumerate(views):
            v.save(output.with_name(f"{output.stem}_view{i}.png"))

    typer.echo("[oky] reconstructing ...")
    cameras = _cameras([30, 90, 150, 210, 270, 330], [20, -10, 20, -10, 20, -10], radius=4.0).to(device)
    n_faces = _reconstruct(model, infer_config, _stack(views).to(device), cameras, output)
    typer.echo(f"[oky] wrote {output} ({n_faces} faces)")


@app.command()
def sheet(
    output: Path = typer.Option(..., "--output", "-o", help="Output GLB path"),
    front: Optional[Path] = typer.Option(None, exists=True, help="Front view"),
    side: Optional[Path] = typer.Option(None, exists=True, help="Side view"),
    back: Optional[Path] = typer.Option(None, exists=True, help="Back view (optional)"),
    sheet_image: Optional[Path] = typer.Option(
        None, "--sheet", exists=True, help="One image with front | side | back left to right"
    ),
    side_azimuth: float = typer.Option(
        90.0, help="Azimuth of the side view. Use 270 if the mesh comes out mirrored front-to-back."
    ),
    mirror_side: bool = typer.Option(
        True, "--mirror-side/--no-mirror-side",
        help="Also use the side view flipped as the opposite side (for symmetric characters)",
    ),
    config: Optional[Path] = typer.Option(None, help="InstantMesh config yaml (default: instant-mesh-large)"),
    save_views: bool = typer.Option(False, help="Also save the framed input views next to the GLB"),
) -> None:
    """Your own front/side/back drawings -> InstantMesh, no imagined views."""
    from rembg import new_session

    session = new_session()
    if sheet_image:
        f_img, s_img, b_img = _split_sheet(Image.open(sheet_image), session)
    else:
        if not front or not side:
            raise typer.BadParameter("pass --sheet, or at least --front and --side")
        f_img = _to_rgba(Image.open(front), session)
        s_img = _to_rgba(Image.open(side), session)
        b_img = _to_rgba(Image.open(back), session) if back else None

    views, azimuths = [f_img, s_img], [0.0, side_azimuth]
    if b_img is not None:
        views.append(b_img)
        azimuths.append(180.0)
    if mirror_side:
        views.append(s_img.transpose(Image.FLIP_LEFT_RIGHT))
        azimuths.append((side_azimuth + 180.0) % 360.0)
    framed = _frame_views(views)
    if save_views:
        output.parent.mkdir(parents=True, exist_ok=True)
        for az, v in zip(azimuths, framed):
            v.save(output.with_name(f"{output.stem}_az{int(az)}.png"))

    device, model, infer_config = _setup(config)
    typer.echo(f"[oky] reconstructing from {len(framed)} views at azimuths {azimuths} ...")
    cameras = _cameras(azimuths, [0.0] * len(azimuths), radius=4.0).to(device)
    n_faces = _reconstruct(model, infer_config, _stack(framed).to(device), cameras, output)
    typer.echo(f"[oky] wrote {output} ({n_faces} faces)")


if __name__ == "__main__":
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    app()
