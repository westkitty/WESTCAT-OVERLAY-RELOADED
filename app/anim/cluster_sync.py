from __future__ import annotations

import glob
import json
import math
import os
import re
import time
import zipfile
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class ClusterSpec:
    name: str
    frames: List[str]
    fps: float = 12.0
    loop: bool = True
    hold_last_ms: int = 0
    easing: Optional[str] = None  # "linear" | "out_cubic" | "out_back"
    zip_path: Optional[str] = None  # optional PNG zip container


@dataclass
class FrameInfo:
    cluster: str
    ms_in: int
    p: float
    frame_idx: int
    frame_path: str


def _ease_linear(p: float) -> float:
    return p


def _ease_out_cubic(p: float) -> float:
    return 1 - (1 - p) ** 3


def _ease_out_back(p: float, s: float = 1.70158) -> float:
    return 1 + (s + 1) * (p - 1) ** 3 + s * (p - 1) ** 2


_EASERS = {
    None: _ease_linear,
    "linear": _ease_linear,
    "out_cubic": _ease_out_cubic,
    "out_back": _ease_out_back,
}


def _collect_frames(entry) -> List[str]:
    if isinstance(entry, dict):
        if "frames" in entry and isinstance(entry["frames"], list):
            return [str(p) for p in entry["frames"]]
        if "glob" in entry:
            return sorted(glob.glob(str(entry["glob"])))
        if "zip" in entry and "fmt" in entry and "range" in entry:
            start, end = entry["range"][:2]
            step = entry["range"][2] if len(entry["range"]) > 2 else 1
            fmt = str(entry["fmt"])
            return [fmt % i for i in range(int(start), int(end) + 1, int(step))]
    if isinstance(entry, list):
        return [str(p) for p in entry]
    if isinstance(entry, str):
        return sorted(glob.glob(entry))
    return []


def load_clusters(json_path: str) -> Dict[str, ClusterSpec]:
    with open(json_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    result: Dict[str, ClusterSpec] = {}
    clusters = data.get("clusters", {})
    for name, entry in clusters.items():
        frames = _collect_frames(entry.get("frames", entry))
        if not frames:
            frames = _collect_frames(entry)
        fps = float(entry.get("fps", 12))
        loop = bool(entry.get("loop", True))
        hold_last_ms = int(entry.get("hold_last_ms", 0))
        easing = entry.get("easing")
        zip_path = entry.get("zip")
        if zip_path and not os.path.exists(zip_path):
            zip_path = None
        if zip_path and not frames:
            frames = _zip_discover_frames(zip_path)
        result[name] = ClusterSpec(
            name=name,
            frames=frames,
            fps=fps,
            loop=loop,
            hold_last_ms=hold_last_ms,
            easing=easing,
            zip_path=zip_path,
        )
    return result


def _zip_discover_frames(zip_path: str) -> List[str]:
    if not os.path.exists(zip_path):
        return []
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = [name for name in zf.namelist() if name.lower().endswith(".png")]
    except Exception:
        return []

    def sort_key(name: str):
        matches = re.findall(r"(\d+)", name)
        if not matches:
            return (name,)
        return tuple(int(m) for m in matches[-2:])

    names.sort(key=sort_key)
    return names


class Animator:
    def __init__(self, clusters: Dict[str, ClusterSpec]):
        self.clusters = clusters
        self._cur: Optional[ClusterSpec] = None
        self._start_ms: int = 0
        self._paused: bool = False
        self._fps_override: Optional[float] = None
        self._providers: Dict[str, object] = {}
        self._last_tick: Optional[FrameInfo] = None

    def set_cluster(self, name: str, now_ms: Optional[int] = None) -> None:
        spec = self.clusters.get(name)
        if not spec:
            return
        self._cur = spec
        self._start_ms = int(now_ms if now_ms is not None else time.time() * 1000)

    def set_paused(self, paused: bool) -> None:
        self._paused = paused

    def toggle_paused(self) -> None:
        self._paused = not self._paused

    def set_fps_override(self, fps: Optional[float]) -> None:
        self._fps_override = fps

    def play(self) -> None:
        self._paused = False

    def pause(self) -> None:
        self._paused = True

    def is_paused(self) -> bool:
        return self._paused

    def tick(self, now_ms: Optional[int] = None) -> Optional[FrameInfo]:
        if self._cur is None:
            return None
        if self._paused and self._last_tick is not None:
            return self._last_tick
        now = int(now_ms if now_ms is not None else time.time() * 1000)
        elapsed = max(0, now - self._start_ms)
        spec = self._cur
        frames = spec.frames
        if not frames:
            return None
        fps = self._fps_override if self._fps_override is not None else spec.fps
        fps = max(1e-6, float(fps))

        if spec.loop:
            period_ms = int(1000 * len(frames) / fps)
            period_ms = max(1, period_ms)
            frame_offset = (elapsed % period_ms) * fps / 1000.0
            idx = int(math.floor(frame_offset)) % len(frames)
            p = (elapsed % period_ms) / period_ms
        else:
            base_duration = 1000 * (len(frames) - 1) / fps if len(frames) > 1 else 0
            dur_ms = int(base_duration + spec.hold_last_ms)
            dur_ms = max(1, dur_ms)
            raw = min(1.0, max(0.0, elapsed / dur_ms))
            ease = _EASERS.get(spec.easing, _ease_linear)
            p = ease(raw)
            if len(frames) == 1:
                idx = 0
            else:
                idx = min(len(frames) - 1, int(math.floor(p * (len(frames) - 1))))
        path = frames[idx]
        fi = FrameInfo(cluster=spec.name, ms_in=elapsed, p=p, frame_idx=idx, frame_path=path)
        self._last_tick = fi
        return fi

    def load_pixmap(self, fi: FrameInfo):
        from PySide6.QtGui import QPixmap

        spec = self.clusters.get(fi.cluster)
        if spec and spec.zip_path:
            try:
                from app.anim.zip_stream import ZipFrameStream
                stream = self._providers.get(spec.zip_path)
                if stream is None:
                    stream = ZipFrameStream(spec.zip_path)
                    self._providers[spec.zip_path] = stream
                return stream.get_pixmap(fi.frame_path)
            except Exception:
                return QPixmap()
        return QPixmap(fi.frame_path)

    # helper for tests
    def frame_for_progress(self, name: str, p: float) -> int:
        spec = self.clusters[name]
        p = max(0.0, min(1.0, p))
        fps = max(1e-6, spec.fps)
        if spec.loop:
            return int(math.floor(p * len(spec.frames))) % len(spec.frames)
        ease = _EASERS.get(spec.easing, _ease_linear)
        ep = ease(p)
        if not spec.frames:
            return 0
        return min(len(spec.frames) - 1, int(math.floor(ep * (len(spec.frames) - 1))))

    def names(self) -> List[str]:
        return list(self.clusters.keys())


def default_cluster_config() -> Dict[str, ClusterSpec]:
    zip_guess = "assets/transparent_png_frames.zip"
    frames = _zip_discover_frames(zip_guess)
    if frames:
        idle_frames = frames[:180] if len(frames) > 180 else frames
        open_frames = frames[:24] if len(frames) >= 24 else frames[:1]
        finish_frames = frames[-24:] if len(frames) >= 24 else frames[-1:]
        return {
            "open": ClusterSpec("open", open_frames, fps=24, loop=False, hold_last_ms=200, easing="out_back", zip_path=zip_guess),
            "idle": ClusterSpec("idle", idle_frames, fps=24, loop=True, zip_path=zip_guess),
            "speak": ClusterSpec("speak", idle_frames, fps=24, loop=True, zip_path=zip_guess),
            "celebrate": ClusterSpec("celebrate", idle_frames, fps=24, loop=True, zip_path=zip_guess),
            "finish_hold": ClusterSpec("finish_hold", finish_frames, fps=24, loop=False, hold_last_ms=600, zip_path=zip_guess),
        }
    idle_frame = "assets/sequences/transparent_png_frames/overlay_final/frames_png_clean/frame_0001.png"
    return {
        "open": ClusterSpec("open", [idle_frame], fps=12, loop=False, hold_last_ms=400, easing="out_back"),
        "idle": ClusterSpec("idle", [idle_frame], fps=12, loop=True),
        "speak": ClusterSpec("speak", [idle_frame], fps=12, loop=True),
        "celebrate": ClusterSpec("celebrate", [idle_frame], fps=12, loop=True),
        "finish_hold": ClusterSpec("finish_hold", [idle_frame], fps=12, loop=False, hold_last_ms=1000),
    }


def try_load_or_default(json_path: str) -> Dict[str, ClusterSpec]:
    try:
        if os.path.exists(json_path):
            clusters = load_clusters(json_path)
            if clusters:
                return clusters
    except Exception:
        pass
    return default_cluster_config()


STATE_TO_CLUSTER = {
    "on_open": "open",
    "idle": "idle",
    "speaking": "idle",
    "advance": "idle",
    "results": "celebrate",
    "finish": "finish_hold",
}


__all__ = [
    "Animator",
    "ClusterSpec",
    "FrameInfo",
    "STATE_TO_CLUSTER",
    "default_cluster_config",
    "load_clusters",
    "try_load_or_default",
]
