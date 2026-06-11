"""Document upload and retrieval endpoints — personal-use (no auth, local storage)."""

import logging

from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundException
from app.dependencies import get_db
from app.models.document import Document, Section
from app.models.project import Project
from app.schemas.document import DocumentResponse
from app.services.local_storage_service import LocalStorageService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["Documents"])


async def _get_project(project_id: str, db: AsyncSession) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project: Project | None = result.scalar_one_or_none()
    if project is None or project.status == "deleted":
        raise NotFoundException("Project not found")
    return project


@router.get("/projects/{project_id}/documents", response_model=list[DocumentResponse])
async def list_project_documents(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    await _get_project(project_id, db)
    result = await db.execute(
        select(Document)
        .where(Document.project_id == project_id)
        .order_by(Document.created_at.desc())
        .options(selectinload(Document.sections))
    )
    return [DocumentResponse.model_validate(d) for d in result.scalars().all()]


@router.post(
    "/projects/{project_id}/documents",
    response_model=DocumentResponse,
    status_code=201,
)
async def upload_document(
    project_id: str,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
):
    """Upload a document to a project.

    Accepts DOCX or TXT files. The file is stored locally and parsed
    synchronously (inline).
    """
    project = await _get_project(project_id, db)

    contents = await file.read()
    file_size = len(contents)
    original_filename = file.filename or "unnamed"

    # Validate
    from app.services.document_service import DocumentService  # noqa: PLC0415

    doc_service = DocumentService()
    file_type = doc_service.validate_file(original_filename, contents, file_size)

    # Save to local storage
    storage = LocalStorageService()
    storage_path = storage.save_upload(f"{project.id}/{original_filename}", contents)

    # Create DB record
    document = Document(
        project_id=project.id,
        original_filename=original_filename,
        file_type=file_type,
        file_size_bytes=file_size,
        storage_path=storage_path,
        parse_status="parsing",
    )
    db.add(document)
    await db.flush()
    await db.refresh(document)

    # Parse synchronously (no Celery)
    try:
        parse_result = doc_service.parse(contents, file_type)
        document.page_count = parse_result.get("page_count")

        # Create Section records from parsed sections
        sections_data = parse_result.get("sections", [])
        for idx, section_data in enumerate(sections_data):
            section = Section(
                document_id=document.id,
                title=section_data.get("title", f"Section {idx + 1}"),
                level=section_data.get("level", 1),
                content=section_data.get("content", ""),
                page_start=section_data.get("page_start"),
                page_end=section_data.get("page_end"),
                order_index=idx,
            )
            db.add(section)

        document.parse_status = "completed"
        logger.info("Document %s parsed successfully: %d sections", document.id, len(sections_data))
    except Exception as exc:
        document.parse_status = "failed"
        document.parse_error = str(exc)
        logger.error("Document %s parsing failed: %s", document.id, exc)

    await db.flush()
    await db.refresh(document)

    return DocumentResponse.model_validate(document)


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document)
        .where(Document.id == document_id)
        .options(selectinload(Document.sections))
    )
    document: Document | None = result.scalar_one_or_none()
    if document is None:
        raise NotFoundException("Document not found")
    return DocumentResponse.model_validate(document)
