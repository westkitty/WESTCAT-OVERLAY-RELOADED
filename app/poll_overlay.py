from __future__ import annotations

import datetime
import json
import os
import time
from typing import Dict, List, Optional

from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPalette
from PySide6.QtWidgets import QApplication, QFileDialog, QLineEdit, QMenu

try:  # Optional sneeze sound
    from PySide6.QtCore import QUrl
    from PySide6.QtMultimedia import QSoundEffect

    HAVE_SOUND = True
except Exception:  # pragma: no cover - multimedia may be unavailable
    HAVE_SOUND = False
    QSoundEffect = None  # type: ignore
    QUrl = None  # type: ignore

from .bryan_parser import FALLBACK_STEPS, load_bryan_steps
from .window_main import OverlayWindow  # translucent frameless shell

DEMO_QUESTIONS: List[Dict] = [
    {"type": "mcq", "text": "Which cat vibe do you like most?", "choices": ["Curious", "Sleepy", "Playful"]},
    {"type": "mcq", "text": "Pick a color for the overlay:", "choices": ["Blue", "Green", "Purple"]},
    {"type": "text", "text": "How chatty should the cat be?"},
]

CARD_PAD = 20
LINE_SP = 8
FIVE_CLICK_WINDOW_MS = 1200


class PollOverlay(OverlayWindow):
    def __init__(self, questions: Optional[List[Dict]] = None, source_path: Optional[str] = None) -> None:
        super().__init__()
        self.setWindowTitle("WESTCAT — Poll Demo")
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        try:
            self.resize(520, 320)
        except Exception:
            pass

        self._export_dir: Optional[str] = None
        json_path = "assets/demo/bryan_demo.json"
        if os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as handle:
                    loaded = json.load(handle)
                self.questions = loaded if isinstance(loaded, list) else FALLBACK_STEPS
            except Exception:
                self.questions = FALLBACK_STEPS
        elif source_path:
            self.questions = load_bryan_steps(source_path)
        else:
            self.questions = questions or DEMO_QUESTIONS
        if not self.questions:
            self.questions = FALLBACK_STEPS

        self.index = 0
        self.responses: Dict[int, Dict[str, object]] = {}
        self.option_rects: List[QRect] = []
        self.status_msg: str | None = None
        self.status_until = 0.0
        self.finish_time = 0.0
        self._click_times: List[float] = []
        self._text_edit: Optional[QLineEdit] = None
        self._ack_scheduled = False

        self._sneeze: Optional[QSoundEffect] = None
        self._peer = None
        self._alpha = 1.0
        self._drag_origin_win: Optional[QPoint] = None
        self._drag_origin_mouse: Optional[QPoint] = None
        self._dev_panel = None
        if HAVE_SOUND:
            sneeze_path = os.path.join("assets", "sfx", "sneeze.wav")
            if os.path.exists(sneeze_path):
                try:
                    effect = QSoundEffect()
                    effect.setSource(QUrl.fromLocalFile(os.path.abspath(sneeze_path)))
                    effect.setVolume(0.9)
                    self._sneeze = effect
                except Exception:
                    self._sneeze = None

    # ---- helpers ----
    def _show_status(self, text: str, ms: int = 1200) -> None:
        self.status_msg = text
        self.status_until = time.perf_counter() * 1000.0 + ms
        self.update()

    def _current(self) -> Optional[Dict]:
        if 0 <= self.index < len(self.questions):
            return self.questions[self.index]
        return None

    def _advance(self) -> None:
        if self._text_edit is not None:
            self._text_edit.deleteLater()
            self._text_edit = None
        self.index += 1
        self.option_rects = []
        self._click_times.clear()
        self._ack_scheduled = False
        if self.index >= len(self.questions):
            self.finish_time = time.perf_counter() * 1000.0 + 2000
        self.update()

    def _record(self, value: object) -> None:
        cur = self._current()
        if not cur:
            return
        self.responses[self.index] = {"type": cur.get("type", "mcq"), "value": value}

    # ---- input ----
    def keyPressEvent(self, ev) -> None:  # type: ignore[override]
        cur = self._current()
        step_type = cur.get("type") if cur else None
        key = ev.key()

        if step_type == "mcq" and Qt.Key_1 <= key <= Qt.Key_9:
            self._choose(key - Qt.Key_1)
            ev.accept()
            return

        if step_type == "mcq" and ev.text():
            letter = ev.text().strip().upper()
            if len(letter) == 1 and "A" <= letter <= "Z":
                self._choose(ord(letter) - ord("A"))
                ev.accept()
                return

        if key in (Qt.Key_Return, Qt.Key_Enter):
            if cur and self.index in self.responses:
                self._advance()
                ev.accept()
                return

        if key == Qt.Key_Escape:
            self.close()
            ev.accept()
            return

        super().keyPressEvent(ev)

    def mousePressEvent(self, ev) -> None:  # type: ignore[override]
        if ev.button() == Qt.LeftButton:
            pos = ev.position().toPoint()
            in_option = any(rect.contains(pos) for rect in self.option_rects)
            in_text = bool(self._text_edit and self._text_edit.geometry().contains(pos))
            if not in_option and not in_text:
                handle = self.windowHandle()
                if handle and hasattr(handle, "startSystemMove"):
                    try:
                        handle.startSystemMove()
                        self._drag_origin_win = None
                        self._drag_origin_mouse = None
                        ev.accept()
                        return
                    except Exception:
                        pass
                try:
                    global_pos = ev.globalPosition().toPoint()
                except AttributeError:
                    global_pos = ev.globalPos()
                self._drag_origin_win = self.frameGeometry().topLeft()
                self._drag_origin_mouse = global_pos
                ev.accept()
                return

            now_ms = time.perf_counter() * 1000.0
            self._click_times.append(now_ms)
            self._click_times = [t for t in self._click_times if now_ms - t <= FIVE_CLICK_WINDOW_MS]
            if len(self._click_times) >= 5:
                self._on_five_clicks()
                self._click_times.clear()

            if in_option:
                for idx, rect in enumerate(self.option_rects):
                    if rect.contains(pos):
                        self._choose(idx)
                        return
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev) -> None:  # type: ignore[override]
        if ev.buttons() & Qt.LeftButton and self._drag_origin_win is not None and self._drag_origin_mouse is not None:
            try:
                current = ev.globalPosition().toPoint()
            except AttributeError:
                current = ev.globalPos()
            delta = current - self._drag_origin_mouse
            self.move(self._drag_origin_win + delta)
            ev.accept()
            return
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev) -> None:  # type: ignore[override]
        if ev.button() == Qt.LeftButton:
            self._drag_origin_win = None
            self._drag_origin_mouse = None
            ev.accept()
            return
        super().mouseReleaseEvent(ev)

    def _on_five_clicks(self) -> None:
        self.open_dev_menu()

    def open_dev_menu(self) -> None:
        from .dev_panel import DevPanel
        if self._dev_panel is None:
            self._dev_panel = DevPanel(self)
        self._dev_panel.show()
        self._dev_panel.raise_()
        self._dev_panel.activateWindow()

    def trigger_dev(self) -> None:
        self._record("triggered")
        self.open_dev_menu()

    def _play_sneeze(self) -> None:
        if self._sneeze:
            try:
                self._sneeze.play()
                return
            except Exception:
                pass
        try:
            from PySide6.QtGui import QGuiApplication

            QGuiApplication.beep()
        except Exception:
            pass

    def _choose(self, option_index: int) -> None:
        cur = self._current()
        if not cur or cur.get("type") != "mcq":
            return
        choices = cur.get("choices", [])
        if option_index < 0 or option_index >= len(choices):
            return
        if self.index not in self.responses:
            label = choices[option_index]
            self._record(label)
            self._show_status(f"Selected: {label}")
            QTimer.singleShot(300, self._advance)
        self.update()

    # ---- paint ----
    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        width, height = self.width(), self.height()
        now_ms = time.perf_counter() * 1000.0

        if self.index >= len(self.questions):
            card_w = min(500, int(width * 0.85))
            card_h = 140
            card_x = (width - card_w) // 2
            card_y = (height - card_h) // 2

            finish_path = QPainterPath()
            radius = 14
            finish_path.addRoundedRect(card_x, card_y, card_w, card_h, radius, radius)
            tail_w, tail_h = 18, 22
            tail_x = card_x - tail_w
            tail_y = card_y + card_h // 2 - tail_h // 2
            tail_path = QPainterPath()
            tail_path.moveTo(tail_x + tail_w, tail_y)
            tail_path.lineTo(tail_x, tail_y + tail_h // 2)
            tail_path.lineTo(tail_x + tail_w, tail_y + tail_h)
            tail_path.closeSubpath()
            finish_path.addPath(tail_path)

            painter.save()
            painter.setOpacity(self._alpha)
            painter.translate(2, 3)
            painter.fillPath(finish_path, QColor(0, 0, 0, 80))
            painter.translate(-2, -3)
            painter.fillPath(finish_path, QColor(255, 255, 255, 240))
            painter.setPen(QColor(0, 0, 0, 70))
            painter.drawPath(finish_path)
            painter.restore()

            painter.setFont(QFont("Monospace", 16))
            painter.setPen(QColor(32, 32, 32, 230))
            finish_text = "Thanks! Your answers were recorded."
            finish_rect = QRect(card_x + CARD_PAD, card_y + CARD_PAD,
                                 card_w - 2 * CARD_PAD, card_h - 2 * CARD_PAD)
            painter.drawText(finish_rect, Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap, finish_text)

            try:
                os.makedirs("data", exist_ok=True)
                with open("data/poll_responses.json", "w", encoding="utf-8") as handle:
                    json.dump({"answers": self.responses}, handle, indent=2)
            except Exception:
                pass
            painter.end()
            return

        card_w = min(640, int(width * 0.92))
        card_h = min(360, int(height * 0.78))
        card_x = (width - card_w) // 2
        card_y = (height - card_h) // 2

        painter.save()
        painter.setOpacity(self._alpha)
        bubble_path = QPainterPath()
        radius = 14
        bubble_path.addRoundedRect(card_x, card_y, card_w, card_h, radius, radius)
        tail_w, tail_h = 18, 22
        tail_x = card_x - tail_w
        tail_y = card_y + card_h // 2 - tail_h // 2
        tail_path = QPainterPath()
        tail_path.moveTo(tail_x + tail_w, tail_y)
        tail_path.lineTo(tail_x, tail_y + tail_h // 2)
        tail_path.lineTo(tail_x + tail_w, tail_y + tail_h)
        tail_path.closeSubpath()
        bubble_path.addPath(tail_path)

        shadow_path = QPainterPath(bubble_path)
        painter.translate(2, 3)
        painter.fillPath(shadow_path, QColor(0, 0, 0, 80))
        painter.translate(-2, -3)

        painter.fillPath(bubble_path, QColor(255, 255, 255, 240))
        painter.setPen(QColor(0, 0, 0, 70))
        painter.drawPath(bubble_path)
        painter.restore()

        current = self._current() or {}
        step_type = current.get("type", "mcq")

        painter.setFont(QFont("Monospace", 14))
        painter.setPen(QColor(32, 32, 32, 230))
        title = current.get("text", "").strip()
        text_rect = QRect(card_x + CARD_PAD, card_y + CARD_PAD, card_w - 2 * CARD_PAD, card_h)
        text_rect = painter.boundingRect(text_rect, Qt.TextWordWrap, title)
        painter.drawText(text_rect, Qt.TextWordWrap, title)
        content_y = text_rect.bottom() + 16

        if step_type == "ack":
            delay = int(current.get("auto_ms", 2000))
            if not self._ack_scheduled:
                self._ack_scheduled = True
                self._record("auto")

                def _auto_advance() -> None:
                    self._ack_scheduled = False
                    self._advance()

                QTimer.singleShot(delay, _auto_advance)

        if step_type == "text":
            if self._text_edit is None:
                self._text_edit = QLineEdit(self)
                self._text_edit.setPlaceholderText("Type your answer and press Enter…")
                self._text_edit.returnPressed.connect(self._on_text_enter)
                self._text_edit.raise_()
                self._text_edit.show()
                self._text_edit.setFocus()
                self._text_edit.setStyleSheet(
                    "QLineEdit{background:#ffffff; color:#222; border:1px solid rgba(0,0,0,60); padding:6px; border-radius:6px;}"
                )
                try:
                    pal = self._text_edit.palette()
                    pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(110, 110, 110))
                    self._text_edit.setPalette(pal)
                except Exception:
                    pass
            self._text_edit.setGeometry(
                card_x + CARD_PAD,
                card_y + CARD_PAD + 60,
                card_w - 2 * CARD_PAD,
                36,
            )
            self.option_rects = []
        elif step_type == "mcq":
            painter.setFont(QFont("Monospace", 12))
            self.option_rects = []
            y_pos = content_y
            option_height = 36
            for idx, label in enumerate(current.get("choices", [])):
                rect = QRect(card_x + CARD_PAD, y_pos, card_w - 2 * CARD_PAD, option_height)
                painter.setBrush(QColor(0, 0, 0, 20))
                painter.setPen(QColor(0, 0, 0, 60))
                painter.drawRoundedRect(rect, 10, 10)
                painter.setPen(QColor(32, 32, 32, 230))
                painter.drawText(
                    rect.adjusted(10, 0, -10, 0),
                    Qt.AlignVCenter | Qt.AlignLeft,
                    f"{idx + 1}. {label}",
                )
                self.option_rects.append(rect)
                y_pos += option_height + LINE_SP
        else:
            self.option_rects = []

        if self.status_msg and now_ms < self.status_until:
            painter.setFont(QFont("Monospace", 10))
            painter.setPen(QColor(40, 40, 40, 220))
            painter.drawText(card_x + CARD_PAD, card_y + card_h - CARD_PAD, self.status_msg)
        elif self.status_msg and now_ms >= self.status_until:
            self.status_msg = None

        painter.end()

    def set_peer(self, peer_widget) -> None:
        self._peer = peer_widget

    def contextMenuEvent(self, event) -> None:  # type: ignore[override]
        menu = QMenu(self)
        dev_action = menu.addAction("Open Dev Menu")
        dev_action.triggered.connect(self.open_dev_menu)

        folder_action = menu.addAction("Set export folder…")
        folder_action.triggered.connect(self._prompt_export_dir)

        menu.addSeparator()
        close_action = menu.addAction("Close both")
        close_action.triggered.connect(self.close_both)

        menu.exec(event.globalPos())

    def _on_text_enter(self) -> None:
        if not self._text_edit:
            return
        value = self._text_edit.text().strip()
        if not value:
            return
        if self.index not in self.responses:
            self._record(value)
            self._show_status("Answer recorded")
            QTimer.singleShot(200, self._advance)

    def _export_results(self) -> None:
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            lines: List[str] = []
            for idx, step in enumerate(self.questions):
                text = step.get("text", "")
                lines.append(f"{idx + 1}. {text}")
                answer = self.responses.get(idx)
                if answer and answer.get("value") not in (None, ""):
                    lines.append(f"   -> {answer.get('value')}")

            candidates: List[str] = []
            if self._export_dir:
                candidates.append(os.path.join(self._export_dir, f"WestCat_Poll_Results_{timestamp}.txt"))
            try:
                xdg_path = os.path.expanduser("~/.config/user-dirs.dirs")
                desktop_dir = None
                if os.path.exists(xdg_path):
                    with open(xdg_path, "r", encoding="utf-8") as handle:
                        for line in handle:
                            if line.startswith("XDG_DESKTOP_DIR"):
                                desktop_dir = (
                                    line.split("=", 1)[1]
                                    .strip()
                                    .strip('"')
                                    .replace("$HOME", os.path.expanduser("~"))
                                )
                                break
                if desktop_dir:
                    candidates.append(os.path.join(desktop_dir, f"WestCat_Poll_Results_{timestamp}.txt"))
            except Exception:
                pass

            candidates.append(os.path.join(os.path.expanduser("~/Desktop"), f"WestCat_Poll_Results_{timestamp}.txt"))
            os.makedirs("data", exist_ok=True)
            candidates.append(os.path.join("data", f"WestCat_Poll_Results_{timestamp}.txt"))

            written = False
            for export_path in candidates:
                try:
                    directory = os.path.dirname(export_path)
                    if directory:
                        os.makedirs(directory, exist_ok=True)
                    with open(export_path, "w", encoding="utf-8") as handle:
                        handle.write("\n".join(lines))
                    written = True
                    break
                except Exception:
                    continue

            if not written:
                with open(f"WestCat_Poll_Results_{timestamp}.txt", "w", encoding="utf-8") as handle:
                    handle.write("\n".join(lines))
        except Exception:
            pass

    def set_export_dir(self, folder: str) -> None:
        self._export_dir = folder

    def export_now(self) -> None:
        self.export_and_close()

    def _prompt_export_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select export folder")
        if folder:
            self.set_export_dir(folder)

    def close_both(self) -> None:
        if self._dev_panel:
            try:
                self._dev_panel.close()
            except Exception:
                pass
            self._dev_panel = None
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
        self.close()
        self._maybe_quit()

    def export_and_close(self) -> None:
        self._play_sneeze()
        self._export_results()
        self.close_both()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self._dev_panel:
            try:
                self._dev_panel.close()
            except Exception:
                pass
            self._dev_panel = None
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

    @staticmethod
    def _maybe_quit() -> None:
        app = QApplication.instance()
        if not app:
            return
        if not any(w.isVisible() for w in app.topLevelWidgets()):
            app.quit()


def main() -> None:
    app = QApplication.instance() or QApplication([])
    window = PollOverlay()
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
