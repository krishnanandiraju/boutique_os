from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import settings
from app.integrations.ports import MediaStoragePort


class MediaStorageError(ValueError):
    pass


class LocalMediaStorage(MediaStoragePort):
    def __init__(self, base_path: str | Path | None = None) -> None:
        self.base_path = Path(base_path or settings.media_storage_path).expanduser()
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _safe_storage_key(self, merchant_id: int, filename: str) -> str:
        suffix = Path(filename).suffix.lower()
        safe_name = f"{uuid4()}{suffix}"
        now = datetime.now(UTC)
        return f"merchant_{merchant_id}/{now:%Y}/{now:%m}/{now:%d}/{safe_name}"

    def resolve_path(self, storage_key: str) -> Path:
        key = storage_key.strip("/")
        pure = PurePosixPath(key)
        if pure.is_absolute() or ".." in pure.parts:
            raise MediaStorageError("Invalid media storage path")
        resolved = (self.base_path / key).resolve()
        root = self.base_path.resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise MediaStorageError("Invalid media storage path") from exc
        return resolved

    def save(self, file: UploadFile, merchant_id: int, *, item_id: int | None = None) -> tuple[str, Path]:
        if not file.filename:
            raise MediaStorageError("Uploaded file is missing a name")
        storage_key = self._safe_storage_key(merchant_id, file.filename)
        target = self.resolve_path(storage_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("wb") as dst:
            if file.file:
                shutil.copyfileobj(file.file, dst)
        return storage_key, target

    def delete(self, storage_key: str) -> None:
        target = self.resolve_path(storage_key)
        if target.exists():
            target.unlink()

    def exists(self, storage_key: str) -> bool:
        try:
            return self.resolve_path(storage_key).exists()
        except MediaStorageError:
            return False
