from io import BytesIO
from minio import Minio
from minio.error import S3Error

from app.config import settings


def get_minio_client() -> Minio:
    return Minio(
        endpoint=settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
    )


def ensure_bucket_exists() -> None:
    client = get_minio_client()
    if not client.bucket_exists(settings.MINIO_BUCKET):
        client.make_bucket(settings.MINIO_BUCKET)


def upload_file(file_key: str, data: bytes, content_type: str) -> None:
    client = get_minio_client()
    client.put_object(
        bucket_name=settings.MINIO_BUCKET,
        object_name=file_key,
        data=BytesIO(data),
        length=len(data),
        content_type=content_type,
    )


def download_file(file_key: str) -> bytes:
    client = get_minio_client()
    response = client.get_object(settings.MINIO_BUCKET, file_key)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def delete_file(file_key: str) -> None:
    try:
        client = get_minio_client()
        client.remove_object(settings.MINIO_BUCKET, file_key)
    except S3Error:
        pass
