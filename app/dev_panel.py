from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
    QMessageBox,
    QRadioButton,
    QButtonGroup,
    QScrollArea,
    QComboBox,
)


class DevPanel(QWidget):
    """Lightweight developer control panel."""

    def __init__(self, poll_overlay) -> None:
        super().__init__(poll_overlay)
        self.setWindowFlags(Qt.Tool | Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.poll = poll_overlay
        self.setWindowTitle("WESTCAT — Dev Menu")
        self.resize(520, 640)
        self.setMinimumSize(480, 600)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        root.addWidget(scroll)

        content = QWidget(self)
        scroll.setWidget(content)

        lay = QVBoxLayout(content)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)
        self.setStyleSheet(
            """
            QWidget#Card { background: rgba(255,255,255,240); border: 1px solid rgba(0,0,0,60); border-radius: 14px; }
            QLabel { color: #222; font-weight: 600; }
            QPushButton { padding: 6px 10px; }
            """
        )

        card = QWidget(objectName="Card")
        lay.addWidget(card)
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

        button_grid = QVBoxLayout()
        layout.addLayout(button_grid)

        row_actions = QHBoxLayout()
        self.btn_edit = QPushButton("Edit Questions…")
        self.btn_results_view = QPushButton("Results So Far")
        for btn in (self.btn_edit, self.btn_results_view):
            btn.setMinimumWidth(180)
            row_actions.addWidget(btn)
        button_grid.addLayout(row_actions)

        row_actions2 = QHBoxLayout()
        self.btn_choose = QPushButton("Choose Results Folder…")
        self.btn_export = QPushButton("Export Now")
        self.btn_builder = QPushButton("Cluster Builder…")
        for btn in (self.btn_choose, self.btn_export, self.btn_builder):
            btn.setMinimumWidth(180)
            row_actions2.addWidget(btn)
        button_grid.addLayout(row_actions2)

        speed_row = QHBoxLayout()
        speed_row.addWidget(QLabel("Typing Speed:", self))
        self.rb12 = QRadioButton("12 cps", self)
        self.rb24 = QRadioButton("24 cps", self)
        self.rb48 = QRadioButton("48 cps", self)
        self._cps_group = QButtonGroup(self)
        for rb in (self.rb12, self.rb24, self.rb48):
            self._cps_group.addButton(rb)
            speed_row.addWidget(rb)
        speed_row.addStretch(1)
        layout.addLayout(speed_row)

        try:
            anim_row = QHBoxLayout()
            btn_playpause = QPushButton("Play/Pause")
            btn_step = QPushButton("Step")
            anim_row.addWidget(btn_playpause)
            anim_row.addWidget(btn_step)
            layout.addLayout(anim_row)

            self.cmb_cluster = QComboBox(self)
            self.cmb_cluster.setMinimumWidth(200)
            anim_select = QHBoxLayout()
            anim_select.addWidget(QLabel("Cluster:", self))
            anim_select.addWidget(self.cmb_cluster, 1)
            layout.addLayout(anim_select)

            def _cat():
                return getattr(self.poll, "_peer", None)

            try:
                cat = _cat()
                names = cat.anim_list_clusters() if cat and hasattr(cat, "anim_list_clusters") else []
                for name in names:
                    self.cmb_cluster.addItem(name)
            except Exception:
                pass

            def _playpause():
                cat = _cat()
                if cat and hasattr(cat, "anim_pause_toggle"):
                    cat.anim_pause_toggle()

            def _step_once():
                cat = _cat()
                if cat and hasattr(cat, "anim_pause_toggle"):
                    cat.anim_pause_toggle()
                    QTimer.singleShot(120, lambda: (hasattr(cat, "anim_pause_toggle") and cat.anim_pause_toggle()))

            def _set_cluster(name: str):
                cat = _cat()
                if cat and hasattr(cat, "anim_set_cluster"):
                    cat.anim_set_cluster(name)

            btn_playpause.clicked.connect(_playpause)
            btn_step.clicked.connect(_step_once)
            self.cmb_cluster.currentTextChanged.connect(_set_cluster)
        except Exception:
            pass

        layout.addStretch(1)

        close_row = QHBoxLayout()
        layout.addLayout(close_row)
        close_row.addStretch(1)
        self.btn_close = QPushButton("Close")
        close_row.addWidget(self.btn_close)

        self.btn_edit.clicked.connect(self._edit_safe)
        self.btn_results_view.clicked.connect(self._open_results_folder_safe)
        self.btn_choose.clicked.connect(self._choose_folder_safe)
        self.btn_export.clicked.connect(self._export_safe)
        self.btn_close.clicked.connect(self.close)
        self.btn_builder.clicked.connect(self._open_cluster_builder)

        cps = getattr(self.poll, "get_typewriter_cps", lambda: 24)()
        self._apply_typing_selection(cps)
        self.rb12.toggled.connect(lambda checked: checked and self._set_typing_speed(12))
        self.rb24.toggled.connect(lambda checked: checked and self._set_typing_speed(24))
        self.rb48.toggled.connect(lambda checked: checked and self._set_typing_speed(48))

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

    # ---- safe wrappers for parent hooks ----
    def _edit_safe(self) -> None:
        handler = getattr(self.poll, "open_question_editor", None)
        if callable(handler):
            try:
                handler()
                return
            except Exception as exc:
                QMessageBox.warning(self, "Question Editor", f"Could not open question editor:\n{exc}")
        self.open_editor()

    def _choose_folder_safe(self) -> None:
        handler = getattr(self.poll, "choose_results_folder", None)
        if callable(handler):
            try:
                handler()
                return
            except Exception as exc:
                QMessageBox.warning(self, "Results Folder", f"Could not choose folder:\n{exc}")
                return
        self.choose_folder()

    def _open_results_folder_safe(self) -> None:
        handler = getattr(self.poll, "open_results_folder", None)
        if callable(handler):
            try:
                handler()
                return
            except Exception as exc:
                QMessageBox.warning(self, "Results", f"Could not open results folder:\n{exc}")
                return
        QMessageBox.information(self, "Results", "No results folder set yet.")

    def _export_safe(self) -> None:
        handler = getattr(self.poll, "export_now", None)
        if callable(handler):
            try:
                handler()
                return
            except Exception as exc:
                QMessageBox.critical(self, "Export Failed", f"Export crashed:\n{exc}")

    def _set_typing_speed(self, cps: int) -> None:
        handler = getattr(self.poll, "set_typewriter_cps", None)
        if callable(handler):
            handler(int(cps))

    def _apply_typing_selection(self, cps: int) -> None:
        if cps <= 12:
            self.rb12.setChecked(True)
        elif cps >= 48:
            self.rb48.setChecked(True)
        else:
            self.rb24.setChecked(True)

    def refresh_typing_speed(self) -> None:
        cps = getattr(self.poll, "get_typewriter_cps", lambda: 24)()
        self._apply_typing_selection(cps)

    def _open_cluster_builder(self) -> None:
        try:
            from tools.cluster_builder import ClusterBuilder

            builder = ClusterBuilder()
            builder.show()
            builder.raise_()
            builder.activateWindow()
            self._builder = builder
        except Exception as exc:
            try:
                self.btn_builder.setEnabled(False)
                self.btn_builder.setToolTip(f"Cluster Builder unavailable:\n{exc}")
            except Exception:
                pass
            QMessageBox.critical(self, "Cluster Builder", f"Could not open:\n{exc}")
