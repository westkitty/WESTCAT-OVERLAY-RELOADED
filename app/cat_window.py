from __future__ import annotations

import os
import time
from typing import Callable, Optional

from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap, QTransform
from PySide6.QtWidgets import QApplication, QLabel, QHBoxLayout, QMenu, QSlider, QWidget, QWidgetAction

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
                handled = False
                if self._dev_menu_cb:
                    try:
                        self._dev_menu_cb()
                        handled = True
                    except Exception:
                        handled = False
                if not handled and self._on_five:  # fallback to shared hook
                    try:
                        self._on_five()
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

        menu.addSeparator()
        opacity_row = QWidget(menu)
        layout = QHBoxLayout(opacity_row)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)
        layout.addWidget(QLabel("Opacity (Cat)", opacity_row))
        slider = QSlider(Qt.Horizontal, opacity_row)
        slider.setRange(30, 100)
        slider.setValue(max(30, min(100, int(round(self._alpha * 100)))))
        slider.setFixedWidth(160)
        layout.addWidget(slider, 1)
        slider_action = QWidgetAction(menu)
        slider_action.setDefaultWidget(opacity_row)
        menu.addAction(slider_action)
        slider.valueChanged.connect(lambda value: self.set_global_opacity(value / 100.0))

        menu.addSeparator()
        flip_action = menu.addAction("Flip Cat (Mirror)")
        flip_action.setCheckable(True)
        flip_action.setChecked(self._flip)
        flip_action.triggered.connect(lambda checked: (setattr(self, "_flip", bool(checked)), self.update()))

        if self._dev_menu_cb:
            dev_action = menu.addAction("Open Dev Menu")

            def _open_dev_menu() -> None:
                try:
                    self._dev_menu_cb()
                except Exception:
                    pass

            dev_action.triggered.connect(_open_dev_menu)

        close_action = menu.addAction("Close both")

        def do_close() -> None:
            self._close_both()

        close_action.triggered.connect(do_close)

        menu.exec(event.globalPos())

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
