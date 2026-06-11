from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SectionInfo(BaseModel):
    """Section schema for API responses."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: str
    title: str
    level: int
    content: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    order_index: int = 0


class DocumentResponse(BaseModel):
    """Document schema for API responses."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    original_filename: str
    file_type: str
    file_size_bytes: int
    page_count: int | None
    sections: list[SectionInfo] | None = None
    parse_status: str
    parse_error: str | None = None
    created_at: datetime
