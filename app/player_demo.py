from __future__ import annotations

import math
import time
from typing import Optional, Tuple

from PySide6.QtCore import QElapsedTimer, QTimer, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen
from PySide6.QtWidgets import QApplication

from .window_main import OverlayWindow  # reuse translucency + ergonomics


def make_transparent_image(w: int, h: int) -> QImage:
    img = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
    img.fill(0)  # fully transparent
    return img


class MockFrameSource:
    """
    Generates translucent frames in-memory to simulate animation without disk I/O.
    Draws a moving circle + faint grid. Fixed logical size; drawn centered & scaled.
    """

    def __init__(self, w: int = 480, h: int = 480) -> None:
        self.w, self.h = w, h
        self._cache: dict[int, QImage] = {}  # frame_index -> QImage

    def frame(self, index: int) -> QImage:
        index = max(0, int(index))
        if index in self._cache:
            return self._cache[index]
        img = make_transparent_image(self.w, self.h)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing, True)

        # grid
        p.setPen(QColor(255, 255, 255, 22))
        step = 60
        for x in range(0, self.w, step):
            p.drawLine(x, 0, x, self.h)
        for y in range(0, self.h, step):
            p.drawLine(0, y, self.w, y)

        # moving circle (demo content)
        t = index / 60.0  # assume 60 tick basis; will map from fps below
        r = min(self.w, self.h) * 0.18
        cx = self.w * (0.5 + 0.35 * math.cos(2 * math.pi * (t / 4.0)))
        cy = self.h * (0.5 + 0.35 * math.sin(2 * math.pi * (t / 3.0)))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(80, 180, 255, 180))
        p.drawEllipse(int(cx - r), int(cy - r), int(2 * r), int(2 * r))

        # label
        p.setPen(QColor(255, 255, 255, 200))
        f = QFont()
        f.setPointSize(10)
        p.setFont(f)
        p.drawText(10, self.h - 12, f"demo frame {index}")
        p.end()
        self._cache[index] = img
        # prune cache lightly
        if len(self._cache) > 240:  # keep last ~4s at 60fps
            for k in sorted(self._cache.keys())[:-180]:
                self._cache.pop(k, None)
        return img


class DemoWindow(OverlayWindow):
    """
    Reuses OverlayWindow for translucent, on-top shell and adds a timed painter.
    Hotkeys:
      Space = Play/Pause
      H     = Toggle HUD
      [ / ] = Decrease/Increase FPS (15/30/45/60)
      N     = Step one frame when paused
      R     = Re-center (inherited), O = Opacity (inherited), S = Size (inherited), T = Click-through (inherited), Esc = Quit
    """

    def __init__(self) -> None:
        super().__init__()
        self.setFocusPolicy(self.focusPolicy() | Qt.StrongFocus)

        # timing
        self.fps_options = [15, 30, 45, 60]
        self.fps_index = 1  # default 30 fps
        self._playing = True
        self._hud = True
        self._logical_index = 0  # integer frame number

        self._source = MockFrameSource(480, 480)

        self._elapsed = QElapsedTimer()
        self._elapsed.start()
        self._last_tick_ns = self._elapsed.nsecsElapsed()

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.PreciseTimer)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start(10)  # high-rate tick; we regulate by elapsed time

        self._accum_ms = 0.0
        self._last_paint_ms = time.perf_counter() * 1000.0
        self._paint_counter = 0
        self._paint_fps = 0.0

        # status message (short confirmation text after actions)
        self._status_msg: str | None = None
        self._status_until_ms: float = 0.0

    # ---- helpers for short-lived status text ----
    def _show_status(self, msg: str, ms: int = 1200) -> None:
        self._status_msg = msg
        self._status_until_ms = time.perf_counter() * 1000.0 + ms
        self.update()

    # ---------- timing tick ----------
    def _on_tick(self) -> None:
        now_ns = self._elapsed.nsecsElapsed()
        dt_ms = (now_ns - self._last_tick_ns) / 1_000_000.0
        self._last_tick_ns = now_ns

        if self._playing:
            fps = self.fps_options[self.fps_index]
            frame_ms = 1000.0 / float(fps)
            self._accum_ms += dt_ms
            while self._accum_ms >= frame_ms:
                self._logical_index += 1
                self._accum_ms -= frame_ms

        self.update()

    # ---------- input controls ----------
    def keyPressEvent(self, ev) -> None:  # type: ignore[override]
        k = ev.key()
        if k == Qt.Key_Space:
            self._playing = not self._playing
            self._show_status("Play" if self._playing else "Pause")
            ev.accept()
            return
        if k == Qt.Key_BracketLeft:  # [
            self.fps_index = max(0, self.fps_index - 1)
            self._show_status(f"FPS {self.fps_options[self.fps_index]}")
            ev.accept()
            return
        if k == Qt.Key_BracketRight:  # ]
            self.fps_index = min(len(self.fps_options) - 1, self.fps_index + 1)
            self._show_status(f"FPS {self.fps_options[self.fps_index]}")
            ev.accept()
            return
        if k == Qt.Key_H:
            self._hud = not self._hud
            ev.accept()
            return
        if k == Qt.Key_N:
            if not self._playing:
                self._logical_index += 1
                self.update()
                ev.accept()
                return
        # Show help when user types '?' (often Shift + '/')
        if ev.text() == '?':
            self._hud = True
            self._show_status(
                "Keys: Space=Play/Pause  H=HUD  [ / ]=FPS  N=Step  O=Opacity  S=Size  T=Click-through  R=Center  Esc=Quit",
                ms=4000,
            )
            ev.accept()
            return
        super().keyPressEvent(ev)

    # --- intercept overlay actions to show confirmations ---
    def toggle_click_through(self) -> None:
        super().toggle_click_through()
        self._show_status(f"Click-through {'ON' if self._click_through else 'OFF'}")

    def cycle_size(self) -> None:
        super().cycle_size()
        self._show_status(f"Size {self._size_key}")

    def cycle_opacity(self) -> None:
        super().cycle_opacity()
        self._show_status(f"Opacity {int(self._opacity * 100)}%")

    def reset_position(self) -> None:
        super().reset_position()
        self._show_status("Centered")

    # ---------- painting ----------
    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)  # keep the faint rounded rect from base class
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)

        # choose a demo frame
        frame = self._source.frame(self._logical_index)

        # center & scale to fit window while preserving alpha
        win_w, win_h = self.width(), self.height()
        img_w, img_h = frame.width(), frame.height()
        scale = min(win_w / img_w, win_h / img_h)
        draw_w, draw_h = int(img_w * scale), int(img_h * scale)
        x = (win_w - draw_w) // 2
        y = (win_h - draw_h) // 2

        p.drawImage(x, y, frame.scaled(draw_w, draw_h, Qt.KeepAspectRatio, Qt.SmoothTransformation))

        # HUD
        if self._hud:
            now_ms = time.perf_counter() * 1000.0
            self._paint_counter += 1
            if now_ms - self._last_paint_ms >= 500.0:
                self._paint_fps = (self._paint_counter * 1000.0) / (now_ms - self._last_paint_ms)
                self._paint_counter = 0
                self._last_paint_ms = now_ms

            p.setFont(QFont("Monospace", 10))
            p.setPen(QColor(255, 255, 255, 230))
            hud_lines = [
                f"demo: mock frames | frame #{self._logical_index}",
                f"timer fps: {self.fps_options[self.fps_index]}  |  paint fps: {self._paint_fps:.1f}",
                "[Space]=Play/Pause  [H]=HUD  [ [ / ] ]=FPS  [N]=Step (paused)  [Esc]=Quit",
                "[O]=Opacity  [S]=Size  [T]=Click-through  [R]=Center   [?]=Show help",
            ]
            y0 = 24
            for line in hud_lines:
                p.drawText(12, y0, line)
                y0 += 16

        # short status message (on top of everything)
        if self._status_msg:
            now_ms = time.perf_counter() * 1000.0
            if now_ms >= self._status_until_ms:
                self._status_msg = None
            else:
                p.setFont(QFont("Monospace", 11))
                p.setPen(QColor(255, 255, 255, 255))
                p.drawText(12, self.height() - 14, self._status_msg)

        p.end()


def main() -> None:
    # Run the demo window
    app = QApplication.instance() or QApplication([])
    w = DemoWindow()
    w.show()
    app.exec()


if __name__ == "__main__":
    main()
