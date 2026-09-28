"""Store and read uploaded files through Django's default storage (S3 or disk)."""

from __future__ import annotations

import hashlib
import re
import uuid
from collections.abc import Iterator
from typing import IO

from django.conf import settings
from django.core.files.base import File
from django.core.files.storage import default_storage

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")
CHUNK = 1024 * 1024


def safe_name(name: str) -> str:
    base = name.replace("\\", "/").rsplit("/", 1)[-1]
    return _UNSAFE.sub("_", base)[:200] or "file"


def new_key(batch_id: int, name: str) -> str:
    return f"uploads/{batch_id}/{uuid.uuid4().hex}/{safe_name(name)}"


def key_belongs_to_batch(key: str, batch_id: int) -> bool:
    return key.startswith(f"uploads/{batch_id}/") and ".." not in key


def save_upload(batch_id: int, name: str, fileobj: IO[bytes]) -> tuple[str, int, str]:
    """Save an uploaded file; returns (key, size, sha256)."""
    digest, size = hashlib.sha256(), 0
    for chunk in iter(lambda: fileobj.read(CHUNK), b""):
        digest.update(chunk)
        size += len(chunk)
    fileobj.seek(0)
    key = default_storage.save(new_key(batch_id, name), File(fileobj))
    return key, size, digest.hexdigest()


def sha256_of(key: str) -> tuple[str, int]:
    digest, size = hashlib.sha256(), 0
    with default_storage.open(key, "rb") as fh:
        for chunk in iter(lambda: fh.read(CHUNK), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def read_bytes(key: str) -> bytes:
    with default_storage.open(key, "rb") as fh:
        return fh.read()


def read_range(key: str, start: int, end: int) -> bytes:
    with default_storage.open(key, "rb") as fh:
        fh.seek(start)
        return fh.read(max(0, end - start))


def iter_lines(key: str) -> Iterator[bytes]:
    """Stream a stored file line by line (bytes, line endings kept)."""
    with default_storage.open(key, "rb") as fh:
        yield from fh


def presigned_put_url(key: str, expires: int = 3600) -> str:
    """A URL the browser can PUT the file to directly (S3 only)."""
    if not settings.USE_S3:
        raise RuntimeError("Presigned uploads need USE_S3=true")
    import boto3

    client = boto3.client("s3", region_name=settings.AWS_S3_REGION_NAME)
    return client.generate_presigned_url(
        "put_object",
        Params={"Bucket": settings.AWS_STORAGE_BUCKET_NAME, "Key": key},
        ExpiresIn=expires,
    )
