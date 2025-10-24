from __future__ import annotations

import os
import re
import zipfile
from functools import lru_cache
from typing import List

from PySide6.QtCore import QBuffer, QByteArray
from PySide6.QtGui import QImageReader, QPixmap


class ZipFrameStream:
    """Stream PNG frames directly from a .zip archive with LRU caching."""

    def __init__(self, zip_path: str):
        if not os.path.exists(zip_path):
            raise FileNotFoundError(zip_path)
        self._zip = zipfile.ZipFile(zip_path, "r")

    @lru_cache(maxsize=512)
    def get_pixmap(self, member_name: str) -> QPixmap:
        data = self._zip.read(member_name)
        buffer = QBuffer()
        buffer.setData(QByteArray(data))
        buffer.open(QBuffer.ReadOnly)
        reader = QImageReader(buffer, b"png")
        image = reader.read()
        buffer.close()
        return QPixmap.fromImage(image) if not image.isNull() else QPixmap()

    def exists(self, member_name: str) -> bool:
        try:
            self._zip.getinfo(member_name)
            return True
        except KeyError:
            return False

    def namelist(self):
        return self._zip.namelist()

    def list_pngs(self) -> List[str]:
        names = [name for name in self._zip.namelist() if name.lower().endswith('.png')]

        def sort_key(name: str):
            matches = re.findall(r"(\d+)", name)
            if not matches:
                return (name,)
            return tuple(int(m) for m in matches[-2:])

        names.sort(key=sort_key)
        return names
