from __future__ import annotations

import json
import os
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
    QLineEdit,
)

from app.anim.zip_stream import ZipFrameStream

ZIP_DEFAULT = "assets/transparent_png_frames.zip"


class ClusterBuilder(QWidget):
    def __init__(self, zip_path: str = ZIP_DEFAULT) -> None:
        super().__init__()
        self.setWindowTitle("Cluster Builder")
        self.resize(720, 560)
        try:
            self.stream = ZipFrameStream(zip_path)
            self.names = self.stream.list_pngs()
        except FileNotFoundError:
            QMessageBox.critical(self, "Missing ZIP", f"{zip_path} not found.")
            self.stream = None
            QTimer.singleShot(0, self.close)
            return
        if not self.names:
            QMessageBox.critical(self, "No frames", f"No PNG frames discovered in {zip_path}.")
            self.stream = None
            QTimer.singleShot(0, self.close)
            return
        self.cur = 0
        self.max = len(self.names) - 1
        self.mark_a: Optional[int] = None
        self.mark_b: Optional[int] = None

        layout = QVBoxLayout(self)
        self.preview = QLabel("frame preview", self)
        self.preview.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.preview, 1)

        slider_row = QHBoxLayout()
        self.slider = QSlider(Qt.Horizontal, self)
        self.slider.setRange(0, self.max)
        self.slider.valueChanged.connect(self._on_slide)
        slider_row.addWidget(self.slider, 1)
        layout.addLayout(slider_row)

        controls = QHBoxLayout()
        self.inp_name = QLineEdit(self)
        self.inp_name.setPlaceholderText("cluster name (idle_a, blink, celebrate...)")
        self.btn_mark_a = QPushButton("Mark A", self)
        self.btn_mark_b = QPushButton("Mark B", self)
        self.btn_add = QPushButton("Add Range", self)
        controls.addWidget(self.inp_name, 2)
        controls.addWidget(self.btn_mark_a)
        controls.addWidget(self.btn_mark_b)
        controls.addWidget(self.btn_add)
        layout.addLayout(controls)

        self.list = QListWidget(self)
        layout.addWidget(self.list, 1)

        bottom = QHBoxLayout()
        self.btn_load = QPushButton("Open existing…", self)
        self.btn_save = QPushButton("Save clusters.json", self)
        bottom.addWidget(self.btn_load)
        bottom.addWidget(self.btn_save)
        layout.addLayout(bottom)

        play_row = QHBoxLayout()
        self.btn_play = QPushButton("Play/Pause", self)
        play_row.addWidget(self.btn_play)
        layout.addLayout(play_row)

        self.btn_mark_a.clicked.connect(lambda: self._mark("A"))
        self.btn_mark_b.clicked.connect(lambda: self._mark("B"))
        self.btn_add.clicked.connect(self._add_range)
        self.btn_save.clicked.connect(self._save)
        self.btn_load.clicked.connect(self._load_existing)
        self.btn_play.clicked.connect(self._toggle_play)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick_play)
        self.playing = False

        self._show_frame(self.cur)

    def _on_slide(self, value: int) -> None:
        self.cur = value
        self._show_frame(value)

    def _show_frame(self, idx: int) -> None:
        if not self.stream or not self.names:
            return
        idx = max(0, min(idx, self.max))
        name = self.names[idx]
        pix = self.stream.get_pixmap(name)
        if not pix.isNull():
            self.preview.setPixmap(pix.scaled(416, 416, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.setWindowTitle(f"Cluster Builder — frame {idx + 1}/{self.max + 1} — {name}")

    def _mark(self, which: str) -> None:
        if which == "A":
            self.mark_a = self.cur
            self.btn_mark_a.setText(f"A={self.cur + 1}")
        else:
            self.mark_b = self.cur
            self.btn_mark_b.setText(f"B={self.cur + 1}")

    def _add_range(self) -> None:
        name = self.inp_name.text().strip()
        if not name or self.mark_a is None or self.mark_b is None:
            QMessageBox.information(self, "Need range", "Provide a name and mark both A and B.")
            return
        a, b = sorted((self.mark_a, self.mark_b))
        item = QListWidgetItem(f"{name}: {a + 1}-{b + 1}")
        item.setData(Qt.UserRole, (name, a, b))
        self.list.addItem(item)
        self.mark_a = self.mark_b = None
        self.btn_mark_a.setText("Mark A")
        self.btn_mark_b.setText("Mark B")
        self.inp_name.clear()

    def _serialize(self) -> Dict[str, dict]:
        clusters: Dict[str, dict] = {}
        for i in range(self.list.count()):
            name, a, b = self.list.item(i).data(Qt.UserRole)
            frame_slice = self.names[int(a) : int(b) + 1]
            clusters[name] = {
                "zip": ZIP_DEFAULT,
                "frames": frame_slice,
                "fps": 24,
                "loop": name.startswith("idle") or name.endswith("_loop"),
            }
        return {"clusters": clusters}

    def _save(self) -> None:
        data = self._serialize()
        os.makedirs("assets/cat", exist_ok=True)
        path = "assets/cat/clusters.json"
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        QMessageBox.information(self, "Saved", f"Wrote {path}")

    def _load_existing(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open clusters.json", "assets/cat/clusters.json", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception as exc:
            QMessageBox.critical(self, "Load failed", f"{exc}")
            return
        self.list.clear()
        for name, entry in data.get("clusters", {}).items():
            rng = entry.get("range", [1, 1])
            item = QListWidgetItem(f"{name}: {rng[0]}-{rng[1]}")
            item.setData(Qt.UserRole, (name, rng[0], rng[1]))
            self.list.addItem(item)

    def _toggle_play(self) -> None:
        self.playing = not self.playing
        if self.playing:
            self.timer.start(40)
        else:
            self.timer.stop()

    def _tick_play(self) -> None:
        nxt = self.cur + 1
        if nxt > self.max:
            nxt = 1
        self.slider.setValue(nxt)


def main() -> None:
    import sys

    app = QApplication(sys.argv)
    w = ClusterBuilder()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
