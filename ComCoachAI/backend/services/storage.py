from __future__ import annotations

import mimetypes
from pathlib import Path

import boto3

from backend.config import get_settings

settings = get_settings()


def s3_enabled() -> bool:
    return settings.S3_ENABLED and bool(settings.S3_BUCKET_NAME.strip())


def _s3_client():
    return boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
        endpoint_url=f"https://s3.{settings.AWS_REGION}.amazonaws.com",
    )


def _content_type_for(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(str(path))
    return guessed or "application/octet-stream"


def upload_file_to_s3(local_path: str | Path, object_key: str, content_type: str | None = None) -> str:
    if not s3_enabled():
        raise RuntimeError("S3 storage is not enabled.")

    path = Path(local_path)
    extra_args = {}
    if content_type:
        extra_args["ContentType"] = content_type

    _s3_client().upload_file(
        str(path),
        settings.S3_BUCKET_NAME,
        object_key,
        ExtraArgs=extra_args or None,
    )
    return f"s3://{settings.S3_BUCKET_NAME}/{object_key}"


def upload_audio_file(local_path: str | Path, filename: str) -> str:
    object_key = f"{settings.S3_AUDIO_PREFIX.strip('/')}/{filename}"
    return upload_file_to_s3(local_path, object_key, _content_type_for(Path(local_path)))


def upload_report_file(local_path: str | Path, filename: str) -> tuple[str, str]:
    object_key = f"{settings.S3_REPORT_PREFIX.strip('/')}/{filename}"
    s3_uri = upload_file_to_s3(
        local_path,
        object_key,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    presigned_url = _s3_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET_NAME, "Key": object_key},
        ExpiresIn=settings.S3_PRESIGNED_URL_EXPIRE_SECONDS,
    )
    return s3_uri, presigned_url
