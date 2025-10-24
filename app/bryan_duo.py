from __future__ import annotations

from PySide6.QtCore import QPropertyAnimation, QPoint, QTimer, QEasingCurve
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from .cat_window import CatWindow
from .poll_overlay import PollOverlay


def main() -> None:
    app = QApplication.instance() or QApplication([])

    bubble = PollOverlay(source_path="assets/demo/BryanDemoConversation.txt")
    cat = CatWindow(on_five_clicks=bubble.export_and_close, size=(360, 360))
    cat.set_peer(bubble)
    bubble.set_peer(cat)
    cat.set_dev_menu_callback(bubble.open_dev_menu)
    cat.show()

    def show_bubble() -> None:
        screen = QGuiApplication.primaryScreen().availableGeometry()
        cat_width, cat_height = cat.width(), cat.height()
        bubble_width, bubble_height = 520, 320
        right_x = cat.x() + cat_width + 16
        left_x = cat.x() - bubble_width - 16
        by = max(screen.y() + 8, min(cat.y(), screen.bottom() - bubble_height - 8))
        if right_x + bubble_width <= screen.right() - 8:
            bx = right_x
        elif left_x >= screen.left() + 8:
            bx = left_x
        else:
            bx = max(screen.x() + 8, min(cat.x() + cat_width // 2 - bubble_width // 2, screen.right() - bubble_width - 8))

        bubble.resize(bubble_width, bubble_height)
        start_y = screen.y() - bubble_height - 20
        bubble.move(bx, start_y)
        bubble.show()
        bubble.raise_()

        bubble._drop_anim = QPropertyAnimation(bubble, b"pos")  # type: ignore[attr-defined]
        bubble._drop_anim.setStartValue(QPoint(bx, start_y))
        bubble._drop_anim.setEndValue(QPoint(bx, by))
        bubble._drop_anim.setDuration(700)
        bubble._drop_anim.setEasingCurve(QEasingCurve.OutCubic)
        bubble._drop_anim.start()

    QTimer.singleShot(850, show_bubble)

    app.exec()


if __name__ == "__main__":
    main()
