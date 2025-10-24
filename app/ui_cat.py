"""Minimal CatWidgetAnimated stub for standalone overlay."""
import os
from itertools import cycle
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QLabel


class CatWidgetAnimated(QLabel):
    def __init__(self):
        super().__init__("WestCat Overlay running 🐾")
        self.setStyleSheet("background:rgba(0,0,0,0.5);color:white;padding:12px;")
        self._frame = 0
        self._saved_proof = False
        self._palette = cycle(
            (
                "rgba(14, 78, 140, 0.85)",
                "rgba(30, 96, 176, 0.85)",
                "rgba(48, 118, 210, 0.85)",
                "rgba(30, 96, 176, 0.85)",
            )
        )
        self._timer = QTimer(self)
        self._timer.setInterval(120)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _tick(self) -> None:
        self._frame += 1
        color = next(self._palette)
        self.setStyleSheet(
            f"background:{color};color:white;padding:12px;font-size:18px;font-weight:bold;"
        )
        self.setText(f"WestCat Overlay frame {self._frame:03d} 🐾")
        self._save_proof_if_requested()

    def _save_proof_if_requested(self) -> None:
        if self._saved_proof or os.getenv("OVERLAY_SAVE_FRAME", "0") != "1":
            return
        artifacts = Path.cwd() / "artifacts"
        artifacts.mkdir(parents=True, exist_ok=True)
        pixmap = self.grab()
        pixmap.save(str(artifacts / "run_proof.png"))
        self._saved_proof = True
        if os.getenv("OVERLAY_AUTO_QUIT", "1") != "0":
            QTimer.singleShot(350, self._quit_app)

    @staticmethod
    def _quit_app() -> None:
        app = QApplication.instance()
        if app is not None:
            app.quit()
