from __future__ import annotations

import os
import time
from typing import Callable, Optional, List

from PySide6.QtCore import QPoint, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap, QTransform, QKeySequence, QShortcut
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QMenu, QSlider, QWidget, QWidgetAction

try:
    from app.anim.cluster_sync import Animator, try_load_or_default
except Exception:  # pragma: no cover - animation optional
    Animator = None  # type: ignore[assignment]

class _CatAnimatorDriver:
    def __init__(self, widget: "CatWindow") -> None:
        self._widget = widget
        self._anim: Optional[Animator] = None
        self._timer: Optional[QTimer] = None
        self._oneshot_timer: Optional[QTimer] = None
        self._last_path: Optional[str] = None
        self._ui_fps = 30
        self._fallback_svg = "assets/cat/cat.svg"
        self._builder = None
        self._idle_names: List[str] = []
        self._celebrate_names: List[str] = []
        self._finish_names: List[str] = []
        self._phone_names: List[str] = []
        self._random_action_names: List[str] = []
        self._excluded_random = {"arrive", "leaving", "leave", "forwardyawn", "forward_yawn", "open"}
        self._played_arrive = False
        if Animator is None:
            return
        clusters = try_load_or_default("assets/cat/clusters.json")
        self._anim = Animator(clusters)
        self._categorize_clusters()
        self._anim.play()
        self._ensure_timer()

        arrive_name = self._find_cluster_name("arrive")
        if arrive_name and not self._played_arrive:
            self._played_arrive = True
            self._play_one_shot(arrive_name, self._cluster_duration_ms(arrive_name))
        else:
            self._select_idle()

        try:
            shortcut = QShortcut(QKeySequence("Ctrl+Shift+B"), self._widget)
            shortcut.activated.connect(self._open_cluster_builder)
            dev_shortcut = QShortcut(QKeySequence("F12"), self._widget)
            dev_shortcut.activated.connect(lambda: (self._widget._dev_menu_cb and self._widget._dev_menu_cb()))
        except Exception:
            pass

    def _ensure_timer(self) -> None:
        if self._timer or self._anim is None:
            return
        self._timer = QTimer(self._widget)
        self._timer.timeout.connect(self._tick)
        self._timer.start(int(1000 / max(1, self._ui_fps)))

    def _tick(self) -> None:
        if self._anim is None:
            return
        frame = self._anim.tick()
        if not frame:
            return
        path = frame.frame_path
        if path == self._last_path:
            return
        try:
            pix = self._anim.load_pixmap(frame)
        except Exception:
            pix = QPixmap()
        if not pix.isNull():
            self._widget.set_cat_pixmap(pix)
            self._last_path = path
            return
        if self._render_svg_fallback():
            self._last_path = f"svg:{self._fallback_svg}"

    def _render_svg_fallback(self) -> bool:
        if not self._fallback_svg or not os.path.exists(self._fallback_svg):
            return False
        renderer = QSvgRenderer(self._fallback_svg)
        if not renderer.isValid():
            return False
        size = self._widget.size()
        if not size.isValid() or size.isEmpty():
            size = QSize(360, 360)
        pix = QPixmap(size)
        pix.fill(Qt.transparent)
        painter = QPainter(pix)
        renderer.render(painter)
        painter.end()
        self._widget.set_cat_pixmap(pix)
        return True

    def _categorize_clusters(self) -> None:
        if not self._anim:
            return
        names = list(self._anim.clusters.keys())
        lowers = {n: n.lower() for n in names}
        self._idle_names = [n for n, l in lowers.items() if l.startswith("idle")]
        self._celebrate_names = [n for n, l in lowers.items() if any(k in l for k in ("clap", "happy", "sparkle", "celebrate", "excited"))]
        self._finish_names = [n for n, l in lowers.items() if any(k in l for k in ("finish", "goodbye", "leave", "leaving"))]
        self._phone_names = [n for n, l in lowers.items() if any(k in l for k in ("phone", "clipboard"))]
        self._random_action_names = [
            n for n, l in lowers.items()
            if not l.startswith("idle") and l not in self._excluded_random
        ]

    def _find_cluster_name(self, target: str) -> Optional[str]:
        if not self._anim:
            return None
        target = target.lower()
        for name in self._anim.clusters.keys():
            if name.lower() == target:
                return name
        return None

    def _cluster_duration_ms(self, name: str) -> int:
        if not self._anim:
            return 1200
        spec = self._anim.clusters.get(name)
        if not spec:
            return 1200
        if spec.loop:
            return 1200
        frame_count = max(1, len(spec.frames))
        fps = max(1e-6, spec.fps)
        base = int(frame_count / fps * 1000)
        return max(400, min(4000, base + int(spec.hold_last_ms)))

    def _select_idle(self) -> None:
        if not self._anim:
            return
        self._categorize_clusters()
        choices = self._idle_names or list(self._anim.clusters.keys())
        if not choices:
            return
        if len(choices) == 1:
            target = choices[0]
        else:
            from random import choice

            target = choice(choices)
        self._anim.set_cluster(target)

    def _play_one_shot(self, name: str, duration_ms: Optional[int] = None) -> None:
        if not self._anim:
            return
        self._anim.set_cluster(name)
        if self._oneshot_timer:
            self._oneshot_timer.stop()
        timer = QTimer(self._widget)
        timer.setSingleShot(True)
        timer.timeout.connect(self._select_idle)
        timer.start(duration_ms or self._cluster_duration_ms(name))
        self._oneshot_timer = timer

    def _play_from_list(self, names: List[str]) -> None:
        if not names:
            self._select_idle()
            return
        from random import choice

        name = choice(names)
        self._play_one_shot(name)

    def _play_random_action(self) -> None:
        self._categorize_clusters()
        if not self._random_action_names:
            return
        from random import choice

        name = choice(self._random_action_names)
        self._play_one_shot(name)

    def handle_state(self, state: str) -> None:
        if not self._anim:
            return
        self._categorize_clusters()
        s = (state or "").lower()
        if s in ("idle", "on_open"):
            self._select_idle()
            return
        if s in ("advance", "next_question", "question_advance"):
            self._play_random_action()
            return
        if s in ("celebrate", "result", "results"):
            self._play_from_list(self._celebrate_names)
            return
        if s in ("finish", "goodbye"):
            self._play_from_list(self._finish_names)
            return
        if s in ("phone", "clipboard"):
            self._play_from_list(self._phone_names)
            return

    def toggle_pause(self) -> None:
        if self._anim:
            self._anim.toggle_paused()

    def set_cluster(self, name: str) -> None:
        if self._anim:
            self._anim.set_cluster(name)

    def set_fps_override(self, fps: Optional[float]) -> None:
        if self._anim:
            self._anim.set_fps_override(fps)

    def list_clusters(self) -> List[str]:
        if self._anim:
            return list(self._anim.clusters.keys())
        return []

    def _open_cluster_builder(self) -> None:
        try:
            from tools.cluster_builder import ClusterBuilder

            builder = ClusterBuilder()
            builder.show()
            builder.raise_()
            builder.activateWindow()
            self._builder = builder  # keep reference
        except Exception:
            pass


SIZE_PRESETS = {"S": (360, 360), "M": (540, 540), "L": (720, 720)}


def find_cat_frame() -> Optional[str]:
    search_roots = [
        "assets/sequences/transparent_png_frames/overlay_final/frames_png_clean",
        "assets/sequences/transparent_png_frames",
        "assets",
    ]
    for root in search_roots:
        if not os.path.isdir(root):
            continue
        for dirpath, _, files in os.walk(root):
            pngs = sorted(f for f in files if f.lower().endswith(".png"))
            if pngs:
                return os.path.join(dirpath, pngs[0])
    return None


class CatWindow(QWidget):
    """Translucent cat window using a PNG frame, with drag + dev menu controls."""

    def __init__(self, on_five_clicks: Optional[Callable[[], None]] = None, size=(360, 360)) -> None:
        flags = Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint
        super().__init__(None, flags)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.resize(*size)
        self.setWindowTitle("WESTCAT — Cat")

        self._drag_origin_win: Optional[QPoint] = None
        self._drag_origin_mouse: Optional[QPoint] = None
        self._clicks_ms: list[float] = []
        self._on_five = on_five_clicks
        self._peer = None
        self._flip = False
        self._alpha = 1.0
        self._dev_menu_cb: Optional[Callable[[], None]] = None
        handle = self.windowHandle()
        self._system_move_available = bool(handle and hasattr(handle, "startSystemMove"))

        self._pixmap: Optional[QPixmap] = None
        frame = find_cat_frame()
        if frame and os.path.exists(frame):
            try:
                self._pixmap = QPixmap(frame)
            except Exception:
                self._pixmap = None

        self._anim_driver: Optional[_CatAnimatorDriver] = None
        try:
            self._anim_driver = _CatAnimatorDriver(self)
        except Exception:
            self._anim_driver = None

    def set_peer(self, peer_widget) -> None:
        self._peer = peer_widget

    def set_dev_menu_callback(self, cb: Callable[[], None]) -> None:
        self._dev_menu_cb = cb

    def set_cat_size(self, key: str) -> None:
        width, height = SIZE_PRESETS.get(key, SIZE_PRESETS["M"])
        self.resize(width, height)

    def set_global_opacity(self, alpha: float) -> None:
        self._alpha = max(0.3, min(1.0, float(alpha)))
        self.setWindowOpacity(self._alpha)
        self.update()

    def set_cat_pixmap(self, pixmap: QPixmap) -> None:
        self._pixmap = pixmap
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setOpacity(self._alpha)
        if self._flip:
            transform = QTransform()
            transform.translate(self.width(), 0)
            transform.scale(-1, 1)
            painter.setTransform(transform)

        if self._pixmap and not self._pixmap.isNull():
            target = self._pixmap.scaled(QSize(self.width(), self.height()), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            x = (self.width() - target.width()) // 2
            y = (self.height() - target.height()) // 2
            painter.drawPixmap(x, y, target)
        else:
            rect = self.rect().adjusted(6, 6, -6, -6)
            painter.setPen(QPen(QColor(255, 255, 255, 60), 2))
            painter.setBrush(QColor(80, 180, 255, 40))
            painter.drawEllipse(rect)
        painter.end()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.LeftButton:
            now = time.perf_counter() * 1000.0
            self._clicks_ms.append(now)
            self._clicks_ms = [t for t in self._clicks_ms if now - t <= 1200]
            if len(self._clicks_ms) >= 5:
                target = self._on_five or self._dev_menu_cb
                if target:
                    try:
                        target()
                    except Exception:
                        pass
                self._clicks_ms.clear()

            handle = self.windowHandle()
            if handle and hasattr(handle, "startSystemMove"):
                try:
                    handle.startSystemMove()
                    self._drag_origin_win = None
                    self._drag_origin_mouse = None
                    event.accept()
                    return
                except Exception:
                    pass

            try:
                global_pos = event.globalPosition().toPoint()
            except AttributeError:
                global_pos = event.globalPos()
            self._drag_origin_win = self.frameGeometry().topLeft()
            self._drag_origin_mouse = global_pos
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if event.buttons() & Qt.LeftButton and self._drag_origin_win is not None and self._drag_origin_mouse is not None:
            try:
                current = event.globalPosition().toPoint()
            except AttributeError:
                current = event.globalPos()
            delta = current - self._drag_origin_mouse
            self.move(self._drag_origin_win + delta)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.LeftButton:
            self._drag_origin_win = None
            self._drag_origin_mouse = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event) -> None:  # type: ignore[override]
        menu = QMenu(self)

        size_menu = menu.addMenu("Size (Cat)")
        for label in ("S", "M", "L"):
            action = size_menu.addAction(label)
            action.triggered.connect(lambda _=False, k=label: self.set_cat_size(k))

        # Labeled opacity slider for the cat
        menu.addSeparator()
        from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel

        row = QWidget(menu)
        hl = QHBoxLayout(row)
        hl.setContentsMargins(8, 4, 8, 4)
        hl.setSpacing(8)
        lbl = QLabel("Opacity (Cat)", row)
        slider = QSlider(Qt.Horizontal, row)
        slider.setMinimum(30)
        slider.setMaximum(100)
        slider.setValue(max(30, min(100, int(round(self._alpha * 100)))))
        slider.setFixedWidth(160)
        hl.addWidget(lbl)
        hl.addWidget(slider, 1)
        slider_action = QWidgetAction(menu)
        slider_action.setDefaultWidget(row)
        menu.addAction(slider_action)
        slider.valueChanged.connect(lambda value: self.set_global_opacity(value / 100.0))

        menu.addSeparator()
        flip_action = menu.addAction("Flip Cat (Mirror)")
        flip_action.setCheckable(True)
        flip_action.setChecked(self._flip)
        flip_action.triggered.connect(lambda checked: (setattr(self, "_flip", bool(checked)), self.update()))

        dev_action = menu.addAction("Open Dev Menu")

        def _open_dev_menu() -> None:
            target = self._on_five or self._dev_menu_cb
            if target:
                try:
                    target()
                except Exception:
                    pass

        dev_action.triggered.connect(_open_dev_menu)

        close_action = menu.addAction("Close both")

        def do_close() -> None:
            self._close_both()

        close_action.triggered.connect(do_close)

        menu.exec(event.globalPos())

    # Animation control surface (best-effort)
    def anim_pause_toggle(self) -> None:
        if self._anim_driver:
            self._anim_driver.toggle_pause()

    def anim_set_cluster(self, name: str) -> None:
        if self._anim_driver:
            self._anim_driver.set_cluster(name)

    def anim_set_fps_override(self, fps: Optional[float]) -> None:
        if self._anim_driver:
            self._anim_driver.set_fps_override(fps)

    def anim_list_clusters(self) -> List[str]:
        if self._anim_driver:
            return self._anim_driver.list_clusters()
        return []

    def notify_state(self, state: str) -> None:
        if self._anim_driver:
            self._anim_driver.handle_state(state)

    def _handle_five_clicks(self) -> None:
        handled = False
        if self._on_five:
            try:
                self._on_five()
                handled = True
            except Exception:
                handled = False
        if not handled:
            self._close_both()

    def _close_both(self) -> None:
        peer = self._peer
        if peer:
            try:
                if hasattr(peer, "_peer"):
                    peer._peer = None
                if not peer.isHidden():
                    peer.close()
            except Exception:
                pass
        self._peer = None
        self.close()
        self._maybe_quit()

    @staticmethod
    def _maybe_quit() -> None:
        app = QApplication.instance()
        if not app:
            return
        if not any(w.isVisible() for w in app.topLevelWidgets()):
            app.quit()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        peer = self._peer
        self._peer = None
        if peer:
            try:
                if hasattr(peer, "_peer"):
                    peer._peer = None
                if not peer.isHidden():
                    peer.close()
            except Exception:
                pass
        self._maybe_quit()
        super().closeEvent(event)
