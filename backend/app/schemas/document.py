from datetime import datetime
from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: str
    original_filename: str
    file_size: int
    mime_type: str
    status: str
    ocr_text: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
