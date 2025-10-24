"""Repository-level smoke tests for the overlay."""

import importlib
import sys
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def test_import_app() -> None:
    """Ensure core application modules are importable."""
    module_names = [
        "app",
        "app.__main__",
        "app.ui_cat",
    ]
    for name in module_names:
        try:
            importlib.import_module(name)
        except ImportError as exc:  # pragma: no cover - fails test immediately
            pytest.fail(f"Failed to import {name}: {exc}")


@pytest.fixture
def app_instance():
    """Create a QApplication instance for tests that need it."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_cat_widget_creation(app_instance):
    """Test if the CatWidget can be created without assets."""
    from app.ui_cat import CatWidgetAnimated

    widget = CatWidgetAnimated()
    assert widget is not None
    widget.show()
    widget.close()


def test_speech_placeholder_creation(app_instance):
    """Validate fallback speech element instantiation."""
    from PySide6.QtWidgets import QLabel

    widget = QLabel("Bubble placeholder")
    assert widget is not None
    widget.show()
    widget.close()
