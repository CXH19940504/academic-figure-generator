"""Document upload and retrieval endpoints — personal-use (no auth, local storage)."""

import logging

from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundException
from app.dependencies import get_db
from app.models.document import Document, Section
from app.schemas.document import PaperType
from app.models.project import Project, Template
from app.schemas.document import DocumentCreate, DocumentResponse, OutlineGenerateRequest, OutlineGenerateDirectRequest, OutlineGenerateResponse
from app.services.local_storage_service import LocalStorageService
from app.services.deepseek_service import DeepseekService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["Documents"])


async def _get_project(project_id: str, db: AsyncSession) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project: Project | None = result.scalar_one_or_none()
    if project is None or project.status == "deleted":
        raise NotFoundException("Project not found")
    return project


async def _get_project_or_create(project_id: str | None, db: AsyncSession, project_name: str) -> Project:
    if project_id is None:
        # Auto-create or reuse a default project
        result = await db.execute(
            select(Project).where(
                Project.name == project_name,
                Project.status == "active",
            )
        )
        project = result.scalar_one_or_none()
        if project is None:
            project = Project(
                name=project_name,
                description=f"直接创建的{project_name}",
            )
            db.add(project)
            await db.flush()
            await db.refresh(project)
        project_id = project.id
    else:
        project = await _get_project(project_id, db)
    return project


async def _get_template(template_id: str, db: AsyncSession) -> Template:
    result = await db.execute(select(Template).where(Template.id == template_id))
    template: Template | None = result.scalar_one_or_none()
    if template is None:
        raise NotFoundException("Template not found")
    return template


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
    data: DocumentCreate,
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

    # Create DB record with new fields
    document = Document(
        project_id=project.id,
        uuid=data.uuid,
        title=data.title,
        paper_type=data.paper_type,
        subject_code=data.subject_code,
        template_id=data.template_id,
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


@router.post("/outline/generate", response_model=OutlineGenerateResponse)
async def generate_outline(
    data: OutlineGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate an outline from paper information.

    Uses Deepseek AI to analyze the provided information and generate a structured
    outline with the specified parameters.

    Args:
        project_id: 项目ID，用于关联项目模板。
        data: Request body with paper information and generation options.
        db: Database session.

    Returns:
        Generated outline with items and metadata.
    """
    project = await _get_project_or_create(data.project_id, db, "直接生成大纲")
    project_id = project.id
    
    if data.template_id is not None:
        template = await _get_template(data.template_id, db)
        original_filename = template.storage_path.split("/")[-1]
        template_content = template.content
    else:
        template = None
        original_filename = ""
        template_content = ""

    document = Document(
        project_id=project_id,
        uuid="",
        title=data.title,
        paper_type=data.paper_type,
        subject_code=data.subject_code,
        template_id=data.template_id,
        original_filename=original_filename,
        file_type="",
        file_size_bytes=data.word_count,
        storage_path="",
        parse_status="completed",
    )
    db.add(document)
    await db.flush()
    await db.refresh(document)
    document_id = document.id

    service = DeepseekService()

    try:
        params = dict(
            major_name=data.subject_name,
            paper_title=data.title,
            word_count=data.word_count,
            paper_type= (data.degree or "") + " " + PaperType.get_name(data.paper_type),
            template_content=template_content,
        )
        result = await service.generate_outline(params)
        sections = result.get("sections", [])
        # 批量添加Section到数据库
        for idx, section_data in enumerate(sections):
            section = Section(
                document_id=document_id,
                material_type=section_data.get("material_type", 1),
                title=section_data.get("title", f"Section {idx + 1}"),
                level=section_data.get("level", 1),
                order_index=idx,
                content=section_data.get("content", ""),
                page_start=section_data.get("page_start"),
                page_end=section_data.get("page_end"),
            )
            db.add(section)
        await db.flush()
        await db.refresh(document)
        return OutlineGenerateResponse(
            success=True,
            message="大纲生成成功",
            data=params,
            document_id=document_id,
            project_id=project_id,
            duration_ms=result.get("duration_ms", 0),
        )
    except Exception as e:
        raise e


@router.post("/outline/generate-direct", response_model=OutlineGenerateResponse)
async def generate_outline_direct(
    data: OutlineGenerateDirectRequest,
    db: AsyncSession = Depends(get_db),
):
    """使用自定义prompt生成大纲"""
    
    project = await _get_project_or_create(data.project_id, db, "直接生成大纲")
    project_id = project.id
    # 每一次修改prompt，创建新文档记录
    document = Document(
        project_id=project_id,
        uuid="",
        title=data.title,
        original_filename="",
        file_type="",
        file_size_bytes=0,
        storage_path="",
        parse_status="completed",
    )
    db.add(document)
    await db.flush()
    await db.refresh(document)
    document_id = document.id
    
    service = DeepseekService()
    
    try:
        # 使用自定义prompt作为system_prompt
        result = await service.generate_outline_with_custom_prompt(
            system_prompt=data.outline_prompt,
        )
        
        # 解析大纲并创建Section记录
        sections = result.get("sections", [])
        for idx, section_data in enumerate(sections):
            section = Section(
                document_id=document_id,
                title=section_data.get("title", f"Section {idx + 1}"),
                level=section_data.get("level", 1),
                content="",
                page_start=None,
                page_end=None,
                order_index=idx,
            )
            db.add(section)
        
        await db.commit()
        
        return OutlineGenerateResponse(
            success=True,
            message="大纲生成成功",
            document_id=document_id,
            project_id=project_id,
            duration_ms=result.get("duration_ms", 0),
        )
    except Exception as e:
        raise e
