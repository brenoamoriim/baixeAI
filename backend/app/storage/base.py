"""StorageProvider: business code never touches paths directly, so S3 can replace local disk."""

import re
import shutil
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from app.core.config import get_settings

_KEY_RE = re.compile(r"^[a-z0-9_-]+(/[a-z0-9_.-]+)*$")


def new_key(prefix: str, extension: str) -> str:
    """Server-generated key; user-provided names are never used as paths."""
    ext = re.sub(r"[^a-z0-9]", "", extension.lower())[:10]
    return f"{prefix}/{uuid.uuid4().hex}.{ext}" if ext else f"{prefix}/{uuid.uuid4().hex}"


class StorageProvider(ABC):
    @abstractmethod
    def save_file(self, key: str, source: Path) -> None: ...

    @abstractmethod
    def open_path(self, key: str) -> Path: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...


class LocalStorage(StorageProvider):
    def __init__(self, root: str) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        if not _KEY_RE.match(key) or ".." in key:
            raise ValueError("invalid storage key")
        path = (self.root / key).resolve()
        if self.root not in path.parents:
            raise ValueError("storage key escapes root")
        return path

    def save_file(self, key: str, source: Path) -> None:
        target = self._path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)

    def open_path(self, key: str) -> Path:
        path = self._path(key)
        if not path.is_file():
            raise FileNotFoundError(key)
        return path

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()


def get_storage() -> StorageProvider:
    return LocalStorage(get_settings().storage_local_root)
