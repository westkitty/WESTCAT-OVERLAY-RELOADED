from __future__ import annotations

import os
import sys

from PySide6.QtCore import QPoint, QSettings, Qt
from PySide6.QtGui import QColor, QGuiApplication, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import QApplication, QWidget

APP_NAME = "WESTCAT-OVERLAY-RELOADED"
ORG_NAME = "westkitty"

SIZE_PRESETS = {
    "S": (360, 360),
    "M": (540, 540),
    "L": (720, 720),
}


class OverlayWindow(QWidget):
    def __init__(self) -> None:
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)

        # ---- Wayland-friendly translucency & attributes (set early) ----
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        # Settings
        self.settings = QSettings(ORG_NAME, APP_NAME)
        self._click_through = self.settings.value("clickThrough", False, type=bool)
        self._opacity = float(self.settings.value("opacity", 0.95))
        self._size_key = self.settings.value("sizeKey", "M")
        if self._size_key not in SIZE_PRESETS:
            self._size_key = "M"

        w, h = SIZE_PRESETS[self._size_key]
        self.resize(w, h)
        self.setWindowTitle(APP_NAME)
        self.setMouseTracking(True)
        self._drag_pos: QPoint | None = None

        # Restore position
        pos_x = self.settings.value("posX", None, type=int)
        pos_y = self.settings.value("posY", None, type=int)
        if pos_x is not None and pos_y is not None:
            self.move(pos_x, pos_y)
        else:
            self._center_on_primary()

        self._apply_click_through()
        self._apply_opacity()

        # Shortcuts
        QShortcut(QKeySequence("Esc"), self, activated=self.close)
        QShortcut(QKeySequence("T"), self, activated=self.toggle_click_through)
        QShortcut(QKeySequence("S"), self, activated=self.cycle_size)
        QShortcut(QKeySequence("O"), self, activated=self.cycle_opacity)
        QShortcut(QKeySequence("R"), self, activated=self.reset_position)

    # ---------------- Painting ----------------
    def paintEvent(self, event) -> None:  # type: ignore[override]
        # Keep window mostly transparent; draw a very faint guide to verify translucency.
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        # Subtle outline (invisible in screenshots with dark bg if too faint; tune alpha)
        pen = QPen(QColor(255, 255, 255, 40))
        pen.setWidth(2)
        p.setPen(pen)
        p.setBrush(QColor(255, 255, 255, 15))  # faint fill
        r = self.rect().adjusted(4, 4, -4, -4)
        p.drawRoundedRect(r, 18, 18)

    # ---------------- Ergonomics ----------------
    def toggle_click_through(self) -> None:
        self._click_through = not self._click_through
        self._apply_click_through()
        self._persist()

    def _apply_click_through(self) -> None:
        # On Wayland, WA_TransparentForMouseEvents works per-widget.
        self.setAttribute(Qt.WA_TransparentForMouseEvents, self._click_through)

    def cycle_size(self) -> None:
        order = ["S", "M", "L"]
        idx = (order.index(self._size_key) + 1) % len(order)
        self._size_key = order[idx]
        w, h = SIZE_PRESETS[self._size_key]
        self.resize(w, h)
        self._persist()

    def cycle_opacity(self) -> None:
        # Cycle a few sensible steps.
        steps = [1.0, 0.95, 0.85, 0.75, 0.6]
        try:
            i = steps.index(round(self._opacity, 2))
        except ValueError:
            i = 0
        self._opacity = steps[(i + 1) % len(steps)]
        self._apply_opacity()
        self._persist()

    def _apply_opacity(self) -> None:
        self.setWindowOpacity(self._opacity)

    def reset_position(self) -> None:
        self._center_on_primary()
        self._persist()

    def _center_on_primary(self) -> None:
        screen = QGuiApplication.primaryScreen()
        geo = screen.availableGeometry() if screen else self.geometry()
        x = geo.x() + (geo.width() - self.width()) // 2
        y = geo.y() + (geo.height() - self.height()) // 2
        self.move(x, y)

    # ---------------- Drag move (when not click-through) ----------------
    def mousePressEvent(self, ev) -> None:  # type: ignore[override]
        if self._click_through:
            return
        if ev.button() == Qt.LeftButton:
            self._drag_pos = ev.globalPosition().toPoint() - self.frameGeometry().topLeft()
            ev.accept()

    def mouseMoveEvent(self, ev) -> None:  # type: ignore[override]
        if self._click_through:
            return
        if self._drag_pos is not None and ev.buttons() & Qt.LeftButton:
            self.move(ev.globalPosition().toPoint() - self._drag_pos)
            ev.accept()

    def mouseReleaseEvent(self, ev) -> None:  # type: ignore[override]
        if self._click_through:
            return
        if ev.button() == Qt.LeftButton:
            self._drag_pos = None
            self._persist()

    # ---------------- Close/persist ----------------
    def closeEvent(self, ev) -> None:  # type: ignore[override]
        self._persist()
        super().closeEvent(ev)

    def _persist(self) -> None:
        self.settings.setValue("clickThrough", self._click_through)
        self.settings.setValue("opacity", self._opacity)
        self.settings.setValue("sizeKey", self._size_key)
        self.settings.setValue("posX", self.x())
        self.settings.setValue("posY", self.y())


def main() -> None:
    # Independent entry point separate from app/__main__.py
    QGuiApplication.setOrganizationName(ORG_NAME)
    QGuiApplication.setApplicationName(APP_NAME)
    app = QApplication(sys.argv)
    win = OverlayWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
