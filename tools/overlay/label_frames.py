#!/usr/bin/env python3
"""
Local, offline frame clustering & preview-sheet generator.

- Embeds PNG frames with a small pretrained ResNet18 (CPU), clusters them (KMeans),
  and writes groupings to JSON.
- For each cluster, saves a preview sheet (collage) so you can visually identify
  which animation it likely is (idle, blink, sleep, etc.).
- Also writes a simple HTML index to flip through previews quickly.

Usage (from repo root):
    source .venv-label/bin/activate
    python tools/overlay/label_frames.py \
        --frame-dir west_cat_overlay/assets/overlay_final/frames_png_transparent \
        --n-clusters 10 \
        --samples 64 \
        --thumb 128

Outputs:
    - west_cat_overlay/assets/frame_clusters.json         (cluster -> list of files)
    - west_cat_overlay/assets/cluster_previews/cluster_*.png
    - west_cat_overlay/assets/cluster_previews/index.html
"""
import argparse, json, math, os, re, sys, pathlib
from typing import List, Dict

import numpy as np
from PIL import Image, ImageDraw
import torch
from torchvision import models, transforms
from sklearn.cluster import KMeans
from tqdm import tqdm

ROOT = pathlib.Path(__file__).resolve().parents[2]

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--frame-dir", default=str(ROOT / "assets" / "overlay_final" / "frames_png_transparent"),
                   help="Directory with transparent PNG frames")
    p.add_argument("--n-clusters", type=int, default=10, help="How many clusters to find")
    p.add_argument("--samples", type=int, default=64, help="Samples per preview sheet")
    p.add_argument("--thumb", type=int, default=128, help="Thumbnail side (px) for preview sheet")
    return p.parse_args()

def load_resnet18_cpu():
    # Newer torchvision API (preferred)
    try:
        from torchvision.models import resnet18, ResNet18_Weights
        weights = ResNet18_Weights.IMAGENET1K_V1
        model = resnet18(weights=weights)
    except Exception:
        # Fallback for older versions
        model = models.resnet18(pretrained=True)
    model.fc = torch.nn.Identity()
    model.eval().to(torch.device("cpu"))
    return model

def list_frames(frame_dir: pathlib.Path) -> List[pathlib.Path]:
    return sorted(frame_dir.glob("*.png"))

_rx_frame_num = re.compile(r"-f(\d+)\.png$", re.IGNORECASE)

def numeric_frame_key(name: str) -> int:
    m = _rx_frame_num.search(name)
    if m: 
        try: return int(m.group(1))
        except: pass
    return 0

def embed_frames(paths: List[pathlib.Path], model, preproc) -> np.ndarray:
    embs = []
    for p in tqdm(paths, desc="Embedding frames"):
        try:
            img = Image.open(p).convert("RGB")
            t = preproc(img).unsqueeze(0)  # [1,C,H,W]
            with torch.no_grad():
                emb = model(t).cpu().numpy().reshape(-1)
            embs.append(emb)
        except Exception as e:
            print(f"skip {p}: {e}")
            embs.append(np.zeros((512,), dtype=np.float32))  # keep index alignment
    return np.stack(embs, axis=0)

def kmeans_cluster(X: np.ndarray, k: int) -> np.ndarray:
    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    return km.fit_predict(X)

def checkerboard(width: int, height: int, step: int = 16) -> Image.Image:
    """Create an RGBA checkerboard (like editors use for transparency)."""
    im = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    on = (200, 200, 200, 255)
    off = (160, 160, 160, 255)
    for y in range(0, height, step):
        for x in range(0, width, step):
            color = on if ((x // step) + (y // step)) % 2 == 0 else off
            draw.rectangle([x, y, x+step, y+step], fill=color)
    return im

def save_preview_sheet(files: List[pathlib.Path], out_png: pathlib.Path, thumb: int, samples: int):
    """Create a grid of thumbnails sampled evenly across 'files'."""
    if not files:
        return
    n = min(samples, len(files))
    # Evenly spaced indices across the sequence
    idxs = np.linspace(0, len(files)-1, n, dtype=int)
    picks = [files[i] for i in idxs]

    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    cell = thumb
    margin = 8
    W = cols * cell + (cols + 1) * margin
    H = rows * cell + (rows + 1) * margin

    # Checkerboard base to reveal transparency artifacts
    base = checkerboard(W, H, step=16)

    x = y = 0
    col = 0
    for i, p in enumerate(picks):
        try:
            img = Image.open(p).convert("RGBA")
            img.thumbnail((cell, cell), Image.LANCZOS)
            # center within cell
            ox = margin + col * (cell + margin) + (cell - img.width) // 2
            oy = margin + y * (cell + margin) + (cell - img.height) // 2
            base.alpha_composite(img, (ox, oy))
        except Exception as e:
            print(f"preview skip {p}: {e}")

        col += 1
        if col >= cols:
            col = 0
            y += 1

    base.save(out_png)

def write_html_index(preview_dir: pathlib.Path, group_meta: Dict[int, int]):
    html = ["<!doctype html><meta charset='utf-8'><title>Cluster Previews</title>",
            "<style>body{font-family:sans-serif;margin:24px} .g{margin-bottom:24px} img{max-width:100%}</style>",
            "<h1>Cluster Previews</h1>"]
    for k in sorted(group_meta.keys()):
        png = f"cluster_{k:02d}.png"
        html.append(f"<div class='g'><h2>Cluster {k} — {group_meta[k]} frames</h2>")
        html.append(f"<img src='{png}' alt='Cluster {k}' loading='lazy'></div>")
    (preview_dir / "index.html").write_text("\n".join(html), encoding="utf-8")

def main():
    args = parse_args()
    frame_dir = pathlib.Path(args.frame_dir)
    out_json = ROOT / "assets" / "frame_clusters.json"
    preview_dir = ROOT / "assets" / "cluster_previews"
    preview_dir.mkdir(parents=True, exist_ok=True)

    paths = list_frames(frame_dir)
    if not paths:
        print(f"No PNG files found in {frame_dir}")
        sys.exit(1)

    # Deterministic name order before embedding
    paths = sorted(paths, key=lambda p: (p.name, numeric_frame_key(p.name)))

    model = load_resnet18_cpu()
    preproc = transforms.Compose([
        transforms.Resize((128, 128)),
        transforms.ToTensor(),
    ])

    X = embed_frames(paths, model, preproc)
    labels = kmeans_cluster(X, args.n_clusters)

    groups = {}
    for p, lbl in zip(paths, labels):
        groups.setdefault(int(lbl), []).append(p.name)

    # Save grouping JSON
    out_json.write_text(json.dumps(groups, indent=2), encoding="utf-8")
    print(f"Wrote {out_json} with {len(groups)} clusters")

    # Per-cluster preview sheets
    group_sizes = {}
    for lbl, names in sorted(groups.items(), key=lambda kv: kv[0]):
        files = [frame_dir / n for n in sorted(names, key=numeric_frame_key)]
        out_png = preview_dir / f"cluster_{lbl:02d}.png"
        save_preview_sheet(files, out_png, thumb=args.thumb, samples=args.samples)
        group_sizes[int(lbl)] = len(files)
        print(f"Preview: {out_png} ({len(files)} frames)")

    # HTML index for quick browsing
    write_html_index(preview_dir, group_sizes)
    print(f"Open previews with: nautilus {preview_dir}")
    print("Tip: You can view in your browser by opening index.html")
    
if __name__ == "__main__":
    main()
