from __future__ import annotations

from PySide6.QtCore import QTimer, QRect
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication

from .cat_window import CatWindow
from .poll_overlay import PollOverlay


def main() -> None:
    app = QApplication.instance() or QApplication([])

    bubble = PollOverlay(source_path="assets/demo/BryanDemoConversation.txt")
    bubble.hide()  # start hidden; we'll animate its content after placement
    cat = CatWindow(on_five_clicks=bubble.open_dev_menu, size=(360, 360))
    cat.set_peer(bubble)
    bubble.set_peer(cat)
    cat.set_dev_menu_callback(lambda: bubble.open_dev_menu())
    cat.show()
    QApplication.processEvents()  # ensure cat geometry is current before reading it

    # Safety shortcut: Ctrl+D opens Dev Menu from either window
    QShortcut(QKeySequence("Ctrl+D"), cat, activated=bubble.open_dev_menu)
    QShortcut(QKeySequence("Ctrl+D"), bubble, activated=bubble.open_dev_menu)

    def show_bubble() -> None:
        screen_obj = cat.screen() or QApplication.primaryScreen()
        screen = screen_obj.availableGeometry()
        cat_rect = QRect(cat.x(), cat.y(), cat.width(), cat.height())
        bw, bh = 600, 360

        desired_x = cat_rect.right() + 200
        desired_y = cat_rect.top() - 200
        bx = min(max(desired_x, screen.left() + 8), screen.right() - bw - 8)
        by = min(max(desired_y, screen.top() + 8), screen.bottom() - bh - 8)
        if QRect(bx, by, bw, bh).intersects(cat_rect):
            bx = min(max(cat_rect.left() - 200 - bw, screen.left() + 8), screen.right() - bw - 8)
        if QRect(bx, by, bw, bh).intersects(cat_rect):
            by = screen.top() + 8

        bubble.resize(bw, bh)
        bubble.move(bx, by)
        bubble.show()
        bubble.raise_()

    QTimer.singleShot(300, show_bubble)

    app.exec()


if __name__ == "__main__":
    main()
