from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

COLUMNS = ["type", "text", "choices", "auto_ms"]


def load_steps(json_path: str, text_fallback: Optional[str]) -> List[Dict]:
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, list):
                return data
        except Exception:
            pass
    try:
        from .bryan_parser import load_bryan_steps

        return load_bryan_steps(text_fallback or "")
    except Exception:
        return []


class StepDialog(QDialog):
    """Simple dialog for adding a question without editing JSON."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Add Question")
        layout = QFormLayout(self)
        self.combo = QComboBox()
        self.combo.addItems([
            "Multiple choice",
            "Short answer",
            "Acknowledge (auto-advance)",
            "Final trigger",
        ])
        self.text_field = QTextEdit()
        self.text_field.setPlaceholderText("Question or message to display…")
        self.choice_field = QLineEdit()
        self.choice_field.setPlaceholderText("Comma-separated choices for multiple choice")
        self.delay_field = QLineEdit()
        self.delay_field.setPlaceholderText("Auto advance delay in ms (acknowledge only)")
        layout.addRow("Type:", self.combo)
        layout.addRow("Text:", self.text_field)
        layout.addRow("Choices:", self.choice_field)
        layout.addRow("Auto delay (ms):", self.delay_field)
        buttons = QHBoxLayout()
        layout.addRow(buttons)
        ok = QPushButton("Add")
        cancel = QPushButton("Cancel")
        buttons.addStretch(1)
        buttons.addWidget(ok)
        buttons.addWidget(cancel)
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)

    def to_step(self) -> Dict:
        text = self.text_field.toPlainText().strip()
        selected = self.combo.currentText()
        if selected == "Multiple choice":
            choices = [c.strip() for c in self.choice_field.text().split(",") if c.strip()]
            return {"type": "mcq", "text": text, "choices": choices}
        if selected == "Short answer":
            return {"type": "text", "text": text}
        if selected == "Acknowledge (auto-advance)":
            try:
                delay = int(self.delay_field.text().strip()) if self.delay_field.text().strip() else 3000
            except Exception:
                delay = 3000
            return {"type": "ack", "text": text, "auto_ms": delay}
        return {"type": "ack_trigger", "text": text or "Click five times to finish and open the Dev Menu."}


class QuestionEditor(QWidget):
    """Table-based editor with add/remove/reorder/import/export controls."""

    def __init__(self, json_path: str, text_fallback: Optional[str] = None):
        super().__init__(flags=Qt.Tool | Qt.WindowStaysOnTopHint)
        self.json_path = json_path
        self.setWindowTitle("WESTCAT — Question Editor")
        self.resize(820, 460)

        root = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        root.addLayout(toolbar)
        toolbar.addWidget(QLabel("Questions (drag rows to reorder; no raw JSON)."))
        toolbar.addStretch(1)
        self.btn_add = QPushButton("＋ Add")
        self.btn_remove = QPushButton("－ Remove")
        self.btn_import = QPushButton("Import…")
        self.btn_export = QPushButton("Export…")
        self.btn_save = QPushButton("Save")
        for button in (self.btn_add, self.btn_remove, self.btn_import, self.btn_export, self.btn_save):
            toolbar.addWidget(button)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setDragEnabled(True)
        self.table.setAcceptDrops(True)
        self.table.setDragDropMode(QTableWidget.DragDropMode.InternalMove)
        root.addWidget(self.table)

        steps = load_steps(json_path, text_fallback)
        for step in steps:
            self._append_row(step)

        self.btn_add.clicked.connect(self._add_step)
        self.btn_remove.clicked.connect(self._delete_selected)
        self.btn_save.clicked.connect(self._save)
        self.btn_import.clicked.connect(self._import_json)
        self.btn_export.clicked.connect(self._export_json)

    # ---- row helpers -------------------------------------------------
    def _append_row(self, step: Dict) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)

        type_combo = QComboBox()
        type_combo.addItems(["ack", "mcq", "text", "ack_trigger"])
        if step.get("type") in ["ack", "mcq", "text", "ack_trigger"]:
            type_combo.setCurrentText(step["type"])
        self.table.setCellWidget(row, 0, type_combo)

        text_edit = QLineEdit(step.get("text", ""))
        text_edit.setClearButtonEnabled(True)
        self.table.setCellWidget(row, 1, text_edit)

        choices = step.get("choices", [])
        choices_str = ", ".join(choices) if isinstance(choices, list) else str(choices or "")
        choices_edit = QLineEdit(choices_str)
        choices_edit.setClearButtonEnabled(True)
        self.table.setCellWidget(row, 2, choices_edit)

        auto_ms = step.get("auto_ms", "")
        auto_edit = QLineEdit(str(auto_ms or ""))
        auto_edit.setClearButtonEnabled(True)
        self.table.setCellWidget(row, 3, auto_edit)

    def _add_step(self) -> None:
        dialog = StepDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._append_row(dialog.to_step())

    def _delete_selected(self) -> None:
        rows = sorted({index.row() for index in self.table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.table.removeRow(row)

    def _gather_steps(self) -> List[Dict]:
        steps: List[Dict] = []
        for row in range(self.table.rowCount()):
            step_type = self.table.cellWidget(row, 0).currentText()
            text = self.table.cellWidget(row, 1).text()
            choices_raw = self.table.cellWidget(row, 2).text()
            auto_raw = self.table.cellWidget(row, 3).text().strip()

            step: Dict = {"type": step_type, "text": text}
            if step_type == "mcq":
                step["choices"] = [c.strip() for c in choices_raw.split(",") if c.strip()]
            if step_type == "ack":
                try:
                    step["auto_ms"] = int(auto_raw) if auto_raw else 3000
                except Exception:
                    step["auto_ms"] = 3000
            if step_type == "ack_trigger" and not step.get("text"):
                step["text"] = "Click five times to finish and open the Dev Menu."
            steps.append(step)
        return steps

    # ---- persistence -------------------------------------------------
    def _save(self) -> None:
        steps = self._gather_steps()
        try:
            os.makedirs(os.path.dirname(self.json_path), exist_ok=True)
            with open(self.json_path, "w", encoding="utf-8") as handle:
                json.dump(steps, handle, indent=2)
            QMessageBox.information(self, "Saved", f"Saved {len(steps)} steps to {self.json_path}")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Could not save:\n{exc}")

    # ---- import / export ---------------------------------------------
    def _import_json(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import Questions", "", "JSON Files (*.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as handle:
                items = json.load(handle)
            if not isinstance(items, list):
                raise ValueError("Unexpected format: expected a list")
            self.table.setRowCount(0)
            for step in items:
                self._append_row(step)
            QMessageBox.information(self, "Imported", f"Loaded {len(items)} questions from:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Could not import:\n{exc}")

    def _export_json(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export Questions", "questions.json", "JSON Files (*.json)")
        if not path:
            return
        steps = self._gather_steps()
        try:
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(steps, handle, indent=2)
            QMessageBox.information(self, "Exported", f"Saved {len(steps)} questions to:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Could not export:\n{exc}")
