from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
    paper_field: str | None = None
    color_scheme: str = "okabe-ito"
    custom_colors: dict | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    paper_field: str | None = None
    color_scheme: str | None = None
    custom_colors: dict | None = None
    status: str | None = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None
    paper_field: str | None
    color_scheme: str | None
    custom_colors: dict | None
    status: str
    created_at: datetime
    updated_at: datetime | None
    document_count: int = 0
    prompt_count: int = 0
    image_count: int = 0


class ProjectListResponse(BaseModel):
    items: list[ProjectResponse]
    total: int
    page: int
    page_size: int


class TemplateResponse(BaseModel):
    """Template schema for API responses."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: Optional[str] = None
    name: str
    storage_path: str | None = None
    created_at: datetime
