from __future__ import annotations

import json
import os
from typing import Iterable, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class QuickQuestionEditor(QDialog):
    """Lightweight fallback editor for Bryan questions."""

    def __init__(self, parent: QWidget | None = None, demo_txt_path: str = "assets/demo/BryanDemoConversation.txt") -> None:
        super().__init__(parent)
        self.setWindowTitle("Quick Question Editor")
        self.resize(560, 420)
        self._demo_txt = demo_txt_path

        root = QVBoxLayout(self)
        self.list = QListWidget(self)
        self.list.setDragDropMode(QAbstractItemView.InternalMove)
        root.addWidget(self.list, 1)

        add_row = QHBoxLayout()
        self.input = QLineEdit(self)
        self.input.setPlaceholderText("Type a question and press +")
        btn_add = QPushButton("+", self)
        btn_add.clicked.connect(self._add_from_input)
        add_row.addWidget(self.input, 1)
        add_row.addWidget(btn_add)
        root.addLayout(add_row)

        controls = QHBoxLayout()
        buttons: List[QPushButton] = [
            QPushButton("Up", self),
            QPushButton("Down", self),
            QPushButton("Remove", self),
            QPushButton("Import JSON…", self),
            QPushButton("Import Demo TXT", self),
            QPushButton("Export JSON", self),
        ]
        (
            btn_up,
            btn_down,
            btn_remove,
            btn_import_json,
            btn_import_demo,
            btn_export,
        ) = buttons
        for btn in buttons:
            controls.addWidget(btn)
        root.addLayout(controls)

        btn_up.clicked.connect(self._move_up)
        btn_down.clicked.connect(self._move_down)
        btn_remove.clicked.connect(self._remove)
        btn_import_json.clicked.connect(self._import_json)
        btn_import_demo.clicked.connect(self._import_demo_txt)
        btn_export.clicked.connect(self._export_json)

    # ---- helpers ----
    def _add_from_input(self) -> None:
        text = self.input.text().strip()
        if not text:
            return
        self.list.addItem(QListWidgetItem(text))
        self.input.clear()

    def _move_up(self) -> None:
        row = self.list.currentRow()
        if row > 0:
            item = self.list.takeItem(row)
            self.list.insertItem(row - 1, item)
            self.list.setCurrentRow(row - 1)

    def _move_down(self) -> None:
        row = self.list.currentRow()
        if 0 <= row < self.list.count() - 1:
            item = self.list.takeItem(row)
            self.list.insertItem(row + 1, item)
            self.list.setCurrentRow(row + 1)

    def _remove(self) -> None:
        row = self.list.currentRow()
        if row >= 0:
            self.list.takeItem(row)

    def _import_json(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open Questions JSON", "", "JSON Files (*.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            texts = self._extract_texts(data)
            if not texts:
                QMessageBox.information(self, "Import", "No questions found in this file.")
                return
            self._load_from_list(texts)
        except Exception as exc:  # pragma: no cover - user driven
            QMessageBox.critical(self, "Import Failed", f"Could not import JSON:\n{exc}")

    def _import_demo_txt(self) -> None:
        path = self._demo_txt
        if not os.path.exists(path):
            QMessageBox.information(self, "Demo Not Found", f"Demo file not found:\n{path}")
            return
        try:
            with open(path, "r", encoding="utf-8") as fh:
                lines = [line.strip() for line in fh.readlines()]
            texts = [line for line in lines if line]
            if not texts:
                QMessageBox.information(self, "Demo Empty", "No non-empty lines in the demo file.")
                return
            self._load_from_list(texts)
        except Exception as exc:  # pragma: no cover - user driven
            QMessageBox.critical(self, "Import Failed", f"Could not import demo text:\n{exc}")

    def _export_json(self) -> None:
        os.makedirs("assets/demo", exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Questions JSON",
            "assets/demo/bryan_demo.json",
            "JSON Files (*.json)",
        )
        if not path:
            return
        try:
            texts = [self.list.item(i).text() for i in range(self.list.count())]
            payload = {"questions": [{"text": txt} for txt in texts]}
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "Saved", f"Exported {len(texts)} question(s) to:\n{path}")
        except Exception as exc:  # pragma: no cover - user driven
            QMessageBox.critical(self, "Export Failed", f"Could not export JSON:\n{exc}")

    def _load_from_list(self, texts: Iterable[str]) -> None:
        self.list.clear()
        for txt in texts:
            if txt:
                self.list.addItem(QListWidgetItem(str(txt)))

    @staticmethod
    def _extract_texts(data) -> List[str]:
        if isinstance(data, dict) and isinstance(data.get("questions"), list):
            return [str(entry.get("text", "")) for entry in data["questions"]]
        if isinstance(data, list):
            return [str(entry) for entry in data]
        return []
