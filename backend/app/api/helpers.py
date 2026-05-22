import json
import uuid
import logging

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.schemas.document import DocumentOut

logger = logging.getLogger(__name__)


def settings_redis() -> str:
    from app.config import settings
    return settings.REDIS_URL


def doc_server_sent(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def doc_to_schema(doc: Document) -> DocumentOut:
    return DocumentOut(
        id=str(doc.id),
        original_filename=doc.original_filename,
        file_size=doc.file_size,
        mime_type=doc.mime_type,
        status=doc.status,
        ocr_text=doc.ocr_text,
        error_message=doc.error_message,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


async def doc_get_owned(doc_id: str, user_id: uuid.UUID, db: AsyncSession) -> Document:
    try:
        uid = uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Document not found")

    result = await db.execute(
        select(Document).where(Document.id == uid, Document.user_id == user_id, Document.deleted == False)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        # Audit log: check if the doc exists but belongs to another user
        exists = await db.execute(select(Document.id).where(Document.id == uid))
        if exists.scalar_one_or_none() is not None:
            logger.warning(
                "document.ownership_violation",
                extra={"doc_id": doc_id, "requesting_user_id": str(user_id)},
            )
        raise HTTPException(status_code=404, detail="Document not found")

    return doc
