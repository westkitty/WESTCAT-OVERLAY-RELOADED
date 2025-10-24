from __future__ import annotations

from PySide6.QtWidgets import QApplication

from .poll_overlay import PollOverlay


def main() -> None:
    app = QApplication.instance() or QApplication([])
    window = PollOverlay(source_path="assets/demo/BryanDemoConversation.txt")
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
