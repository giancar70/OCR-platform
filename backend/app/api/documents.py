import json
import logging
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as aioredis

from app.api.deps import get_current_user
from app.api.helpers import doc_to_schema, doc_get_owned, settings_redis, doc_server_sent
from app.core.pubsub import publish_async, channel
from app.core.security import decode_access_token
from app.core.storage import upload_file, delete_file
from app.database import get_db, AsyncSessionLocal
from app.models.document import Document
from app.models.log import Log
from app.models.users import User
from app.schemas.document import DocumentOut
from app.tasks.ocr import process_document

router = APIRouter(prefix="/documents", tags=["documents"])
logger = logging.getLogger(__name__)

ALLOWED_TYPES = {"image/jpeg", "image/png", "application/pdf"}
MAX_SIZE = 10 * 1024 * 1024  # 10 MB
TERMINAL = {"completed", "failed", "cancelled"}


@router.get("/", response_model=list[DocumentOut])
async def list_documents(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document)
        .where(Document.user_id == current_user.id, Document.deleted == False)
        .order_by(Document.created_at.desc())
    )
    return [doc_to_schema(d) for d in result.scalars().all()]


@router.post("/", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
        file: UploadFile = File(...),
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only JPG, PNG and PDF files are accepted",
        )

    data = await file.read()
    if len(data) > MAX_SIZE:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File exceeds 10 MB limit")

    doc_id = uuid.uuid4()
    safe_name = file.filename or f"file_{doc_id}"
    file_key = f"{current_user.id}/{doc_id}/{safe_name}"

    upload_file(file_key, data, file.content_type)

    doc = Document(
        id=doc_id,
        user_id=current_user.id,
        original_filename=safe_name,
        file_key=file_key,
        file_size=len(data),
        mime_type=file.content_type,
        status="uploaded",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # Dispatch task and immediately move to queued
    task = process_document.delay(str(doc_id), file_key, file.content_type)
    doc.celery_task_id = task.id
    doc.status = "queued"
    doc.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(doc)
    data_extra = {
        "doc_id": str(doc_id),
        "user_id": str(current_user.id),
        "doc_filename": safe_name,
        "size_bytes": len(data),
        "mime_type": file.content_type,
    }
    log = Log(id=uuid.uuid4(), user_id=current_user.id, action='CREATE', request_data=data_extra)
    db.add(log)
    await db.commit()

    logger.info("document.upload", extra=data_extra, )
    return doc_to_schema(doc)


@router.get("/{doc_id}", response_model=DocumentOut)
async def get_document(
        doc_id: str,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
):
    return doc_to_schema(await doc_get_owned(doc_id, current_user.id, db))


@router.post("/{doc_id}/cancel", response_model=DocumentOut)
async def cancel_document(
        doc_id: str,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
):
    doc = await doc_get_owned(doc_id, current_user.id, db)

    if doc.status not in ("uploaded", "queued"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot cancel a document with status '{doc.status}'",
        )

    # Revoke the Celery task (no-op if not yet picked up, ignored if already running)
    if doc.celery_task_id:
        from app.tasks.celery_app import celery_app as _celery
        _celery.control.revoke(doc.celery_task_id, terminate=False)

    doc.status = "cancelled"
    doc.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(doc)

    await publish_async(doc_id, {"status": "cancelled", "ocr_text": None, "error_message": None})

    data_extra = {"doc_id": doc_id, "user_id": str(current_user.id)}
    log = Log(id=uuid.uuid4(), user_id=current_user.id, action='CANCEL', request_data=data_extra)
    db.add(log)
    await db.commit()
    logger.info("document.cancel", extra=data_extra)
    return doc_to_schema(doc)


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
        doc_id: str,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
):
    doc = await doc_get_owned(doc_id, current_user.id, db)
    delete_file(doc.file_key)
    # remove from database
    # await db.execute(delete(Document).where(Document.id == doc.id)) #
    doc.deleted = True
    await db.commit()
    await db.refresh(doc)

    data_extra = {"doc_id": doc_id, "user_id": str(current_user.id)}
    log = Log(id=uuid.uuid4(), user_id=current_user.id, action='DELETE', request_data=data_extra)
    db.add(log)
    await db.commit()
    logger.info("document.delete", extra=data_extra)


@router.get("/{doc_id}/stream")
async def stream_status(
        doc_id: str,
        token: str,
        db: AsyncSession = Depends(get_db),
):
    """token passed as query param because EventSource doesn't support custom headers."""
    username = decode_access_token(token)
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    await doc_get_owned(doc_id, user.id, db)  # ownership check

    async def generator() -> AsyncGenerator[str, None]:
        r = aioredis.from_url(settings_redis())
        pubsub = r.pubsub()
        await pubsub.subscribe(channel(doc_id))

        try:
            # Subscribe BEFORE querying current state to avoid race condition
            async with AsyncSessionLocal() as s:
                res = await s.execute(select(Document).where(Document.id == uuid.UUID(doc_id)))
                current = res.scalar_one_or_none()

            if current:
                yield doc_server_sent(
                    {"status": current.status, "ocr_text": current.ocr_text, "error_message": current.error_message})
                if current.status in TERMINAL:
                    return

            while True:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=5.0)
                if msg is None:
                    yield ": ping\n\n"
                    continue

                if msg["type"] == "message":
                    raw = msg["data"]
                    data = json.loads(raw if isinstance(raw, str) else raw.decode())
                    yield doc_server_sent(data)
                    if data.get("status") in TERMINAL:
                        break

        finally:
            await pubsub.unsubscribe(channel(doc_id))
            await pubsub.aclose()
            await r.aclose()

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

