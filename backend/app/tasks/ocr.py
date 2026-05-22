import logging
import os
import tempfile
import uuid
from datetime import datetime

from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.config import settings
from app.core.pubsub import publish_sync
from app.core.storage import download_file
from app.models.document import Document  # noqa: F401 — registers ORM mappers
from app.models.users import User  # noqa: F401 — needed to resolve Document.owner relationship
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

# Synchronous psycopg2 engine — safe after os.fork(), no event-loop binding.
_sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
_engine = create_engine(_sync_url, poolclass=NullPool)
SyncSession = sessionmaker(_engine, expire_on_commit=False)


def _get_status(doc_uuid: uuid.UUID) -> str | None:
    with SyncSession() as s:
        row = s.execute(select(Document.status).where(Document.id == doc_uuid))
        return row.scalar_one_or_none()


def _set_status(doc_uuid: uuid.UUID, status: str, ocr_text: str | None = None, error_message: str | None = None) -> None:
    values: dict = {"status": status, "updated_at": datetime.utcnow()}
    if ocr_text is not None:
        values["ocr_text"] = ocr_text
    if error_message is not None:
        values["error_message"] = error_message[:500]
    with SyncSession() as s:
        s.execute(update(Document).where(Document.id == doc_uuid).values(**values))
        s.commit()


@celery_app.task(name="app.tasks.ocr.process_document", bind=True, max_retries=2, default_retry_delay=10)
def process_document(self, document_id: str, file_key: str, mime_type: str) -> None:
    doc_uuid = uuid.UUID(document_id)

    try:
        current = _get_status(doc_uuid)
        if current == "cancelled":  # check if is canceled
            logger.info("ocr.skipped_cancelled", extra={"doc_id": document_id})
            return

        logger.info("ocr.started", extra={"doc_id": document_id, "file_key": file_key})
        _set_status(doc_uuid, "processing")
        publish_sync(document_id, {"status": "processing", "ocr_text": None, "error_message": None})

        file_data = download_file(file_key)
        suffix = ".pdf" if mime_type == "application/pdf" else ".png"

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(file_data)
            tmp_path = tmp.name

        try:
            ocr_text = _run_ocr(tmp_path, mime_type)
        finally:
            os.unlink(tmp_path)

        _set_status(doc_uuid, "completed", ocr_text=ocr_text)
        publish_sync(document_id, {"status": "completed", "ocr_text": ocr_text, "error_message": None})
        logger.info("ocr.completed", extra={"doc_id": document_id, "text_length": len(ocr_text)})

    except Exception as exc:
        error_msg = str(exc)
        logger.error(
            "ocr.failed",
            extra={"doc_id": document_id, "error": error_msg, "attempt": self.request.retries + 1},
        )
        try:
            _set_status(doc_uuid, "failed", error_message=error_msg)
            publish_sync(document_id, {"status": "failed", "ocr_text": None, "error_message": error_msg[:500]})
        except Exception:
            pass
        raise self.retry(exc=exc)


def _run_ocr(file_path: str, mime_type: str) -> str:
    provider = settings.OCR_PROVIDER.lower()
    logger.info("ocr.provider", extra={"provider": provider})

    if provider == "openai":
        return _run_openai(file_path, mime_type)
    return _run_tesseract(file_path, mime_type)


def _run_tesseract(file_path: str, mime_type: str) -> str:
    import pytesseract
    from PIL import Image

    if mime_type == "application/pdf":
        from pdf2image import convert_from_path
        pages = convert_from_path(file_path, dpi=200)
        return "\n\n--- Page Break ---\n\n".join(pytesseract.image_to_string(p) for p in pages)

    with Image.open(file_path) as img:
        return pytesseract.image_to_string(img)


def _run_openai(file_path: str, mime_type: str) -> str:
    import base64
    import io
    from openai import OpenAI

    if not settings.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not set — cannot use openai provider")

    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def _extract(image_bytes: bytes, img_mime: str) -> str:
        b64 = base64.b64encode(image_bytes).decode()
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{img_mime};base64,{b64}"},
                    },
                    {
                        "type": "text",
                        "text": (
                            "Extract all the text from this document image. "
                            "Return only the extracted text, preserving the original "
                            "layout as closely as possible. "
                            "If there is no text, return an empty string."
                        ),
                    },
                ],
            }],
            max_tokens=4096,
        )
        return response.choices[0].message.content or ""

    if mime_type == "application/pdf":
        from pdf2image import convert_from_path
        pages = convert_from_path(file_path, dpi=200)
        results = []
        for page in pages:
            buf = io.BytesIO()
            page.save(buf, format="PNG")
            results.append(_extract(buf.getvalue(), "image/png"))
        return "\n\n--- Page Break ---\n\n".join(results)

    with open(file_path, "rb") as f:
        return _extract(f.read(), mime_type)


