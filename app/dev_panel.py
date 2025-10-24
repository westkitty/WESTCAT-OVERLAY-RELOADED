from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)


class DevPanel(QWidget):
    """Lightweight developer control panel."""

    def __init__(self, poll_overlay) -> None:
        super().__init__(flags=Qt.Tool | Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.poll = poll_overlay
        self.setWindowTitle("WESTCAT — Dev Menu")
        self.setFixedSize(420, 300)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        self.setStyleSheet(
            """
            QWidget#Card { background: rgba(255,255,255,240); border: 1px solid rgba(0,0,0,60); border-radius: 14px; }
            QLabel { color: #222; font-weight: 600; }
            QPushButton { padding: 6px 10px; }
            """
        )

        card = QWidget(objectName="Card")
        root.addWidget(card)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("Developer Menu")
        title.setFont(QFont("Monospace", 14))
        layout.addWidget(title)

        row1 = QHBoxLayout()
        layout.addLayout(row1)
        row1.addWidget(QLabel("Animation state:"))
        self.state_combo = QComboBox()
        self.state_combo.addItems(["idle", "blink", "breath", "talk"])
        row1.addWidget(self.state_combo)

        row2 = QHBoxLayout()
        layout.addLayout(row2)
        row2.addWidget(QLabel("Animation speed:"))
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(50, 200)
        self.speed_slider.setValue(100)
        row2.addWidget(self.speed_slider)

        buttons = QHBoxLayout()
        layout.addLayout(buttons)
        self.btn_edit = QPushButton("Edit Questions…")
        self.btn_results = QPushButton("Choose Results Folder…")
        self.btn_export = QPushButton("Export Now")
        buttons.addWidget(self.btn_edit)
        buttons.addWidget(self.btn_results)
        buttons.addWidget(self.btn_export)

        layout.addStretch(1)

        close_row = QHBoxLayout()
        layout.addLayout(close_row)
        close_row.addStretch(1)
        self.btn_close = QPushButton("Close")
        close_row.addWidget(self.btn_close)

        self.btn_edit.clicked.connect(self.open_editor)
        self.btn_results.clicked.connect(self.choose_folder)
        self.btn_export.clicked.connect(self.export_now)
        self.btn_close.clicked.connect(self.close)

    def open_editor(self) -> None:
        from .question_editor import QuestionEditor

        editor = QuestionEditor(
            json_path="assets/demo/bryan_demo.json",
            text_fallback="assets/demo/BryanDemoConversation.txt",
        )
        editor.show()

    def choose_folder(self) -> None:
        dlg = QFileDialog(self, "Select results folder")
        dlg.setFileMode(QFileDialog.FileMode.Directory)
        if dlg.exec():
            dirs = dlg.selectedFiles()
            if dirs:
                self.poll.set_export_dir(dirs[0])

    def export_now(self) -> None:
        self.poll.export_now()
