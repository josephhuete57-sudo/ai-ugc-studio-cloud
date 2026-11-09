"""Almacenamiento cloud: local (por defecto) o S3-compatible.

Local: archivos en CLOUD_STORAGE_DIR, servidos por el backend con token.
S3: subida vía boto3 (si está instalado) y URLs firmadas temporales.
"""
from __future__ import annotations

import hashlib
import shutil
import time
from pathlib import Path

from cloud.common.config import settings


class Storage:
    def __init__(self) -> None:
        self.root = settings.STORAGE_DIR
        self.root.mkdir(parents=True, exist_ok=True)
        self._s3 = None
        if settings.S3_ENDPOINT and settings.S3_BUCKET:
            try:
                import boto3  # type: ignore

                self._s3 = boto3.client(
                    "s3",
                    endpoint_url=settings.S3_ENDPOINT,
                    aws_access_key_id=settings.S3_ACCESS_KEY,
                    aws_secret_access_key=settings.S3_SECRET_KEY,
                )
                self._s3.head_bucket(Bucket=settings.S3_BUCKET)
            except Exception:
                self._s3 = None  # cae a local

    def _key(self, name: str) -> str:
        digest = hashlib.sha256(f"{time.time()}-{name}".encode()).hexdigest()[:12]
        return f"{digest}_{Path(name).name}"

    def save_bytes(self, name: str, data: bytes) -> str:
        key = self._key(name)
        if self._s3 is not None:
            self._s3.put_object(Bucket=settings.S3_BUCKET, Key=key, Body=data)
            return key
        (self.root / key).write_bytes(data)
        return key

    def save_file(self, name: str, src: str | Path) -> str:
        key = self._key(name)
        if self._s3 is not None:
            self._s3.upload_file(str(src), settings.S3_BUCKET, key)
            return key
        shutil.copy2(str(src), str(self.root / key))
        return key

    def exists(self, key: str) -> bool:
        if self._s3 is not None:
            try:
                self._s3.head_object(Bucket=settings.S3_BUCKET, Key=key)
                return True
            except Exception:
                return False
        return (self.root / key).exists()

    def download_to(self, key: str, dest: str | Path) -> Path:
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if self._s3 is not None:
            self._s3.download_file(settings.S3_BUCKET, key, str(dest))
        else:
            shutil.copy2(str(self.root / key), str(dest))
        return dest

    def url(self, key: str) -> str:
        """URL temporal firmada en S3, o ruta con token en local."""
        if self._s3 is not None:
            return self._s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": settings.S3_BUCKET, "Key": key},
                ExpiresIn=3600,
            )
        return f"/api/cloud/files/{key}"


storage = Storage()
