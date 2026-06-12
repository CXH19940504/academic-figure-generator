"""Document upload and retrieval endpoints — personal-use (no auth, local storage)."""

import logging

from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BadRequestException, NotFoundException
from app.dependencies import get_db
from app.models.document import Document, Section
from app.models.prompt import Prompt
from app.schemas import get_subject_name_by_code
from app.schemas.document import MaterialType, PaperType
from app.models.project import Project, Template
from app.schemas.document import (
    DocumentCreate, DocumentResponse, OutlineGenerateRequest, OutlineGenerateResponse,
    OutlinePromptCreateRequest, OutlinePromptResponse
)
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

async def _get_document(document_id: str, db: AsyncSession) -> Document:
    result = await db.execute(select(Document).where(Document.id == document_id))
    document: Document | None = result.scalar_one_or_none()
    if document is None:
        raise NotFoundException("Document not found")
    return document


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


async def _get_prompt(prompt_id: str, db: AsyncSession) -> Prompt:
    result = await db.execute(select(Prompt).where(Prompt.id == prompt_id))
    prompt: Prompt | None = result.scalar_one_or_none()
    if prompt is None:
        raise NotFoundException("Prompt not found")
    return prompt


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
        section_count = await _save_sections_to_db(parse_result, document.id, db)

        document.parse_status = "completed"
        logger.info("Document %s parsed successfully: %d sections", document.id, section_count)
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


def _build_outline_system_prompt(params: dict) -> str:
    """构建大纲生成的 system prompt"""
    from app.services.deepseek_service import DeepseekService, SystemPromptName
    service = DeepseekService()
    system_prompt = service._get_skill_content(SystemPromptName.OUTLINE.value)
    for key, value in params.items():
        system_prompt = system_prompt.replace("{% " + key + " %}", str(value or ""))
    return system_prompt


async def _save_sections_to_db(result: dict, document_id: str, db: AsyncSession) -> int:
    """将大纲数据保存到数据库"""
    logger = logging.getLogger(__name__)
    logger.info("_save_sections_to_db called, result keys: %s, document_id: %s", list(result.keys()), document_id)

    sections = result.get("data", [])
    logger.info("_save_sections_to_db: found %d sections in result", len(sections))

    for idx, section_data in enumerate(sections):
        title = section_data.get("title", f"Section {idx + 1}")
        level = section_data.get("level", 1)
        logger.info("_save_sections_to_db: saving section [%d] title=%s level=%s", idx, title, level)
        section = Section(
            document_id=document_id,
            title=title,
            level=level,
            content="",
            page_start=None,
            page_end=None,
            order_index=idx,
        )
        db.add(section)

    await db.flush()
    logger.info("_save_sections_to_db: flushed %d sections to DB", len(sections))
    return len(sections)


@router.post("/outline/prompt", response_model=OutlinePromptResponse)
async def create_outline_prompt(
    data: OutlinePromptCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """创建大纲Prompt并插入数据库。

    Args:
        data: Request body with paper information.
        db: Database session.

    Returns:
        Created prompt with ID and system prompt.
    """
    # 1. 获取或创建项目
    project = await _get_project_or_create(data.project_id, db, "直接生成大纲")
    project_id = project.id

    # 2. 获取模板
    if data.template_id is not None:
        template = await _get_template(data.template_id, db)
    else:
        raise BadRequestException("template_id is required")
    template_content = template.content

    # 3.获取或创建文档
    if data.document_id is not None:
        document = await _get_document(data.document_id, db)
    else:
        # 创建 Document
        document = Document(uuid="", storage_path="")
    
    document.project_id = project_id
    document.title = data.title
    document.paper_type = data.paper_type
    document.subject_code = data.subject_code
    document.template_id = data.template_id
    document.original_filename = template.storage_path.split("/")[-1]
    document.file_type = template.storage_path.split(".")[-1]
    document.file_size_bytes = data.word_count
    document.parse_status = "generating"
    if data.document_id is None:
        db.add(document)
        await db.flush()
    await db.refresh(document)
    document_id = document.id

    # 4. 构建 system prompt
    params = {
        "major_name": get_subject_name_by_code(data.subject_code),
        "paper_title": data.title,
        "word_count": data.word_count,
        "paper_type": data.degree or "" + PaperType.get_name(data.paper_type),
        "template_content": template_content,
    }
    system_prompt = _build_outline_system_prompt(params)

    # 5. 获取或创建 Prompt
    if data.prompt_id is not None:
        prompt = await _get_prompt(data.prompt_id, db)
    else:
        prompt = Prompt(
            project_id=project_id,
            document_id=document_id,
            figure_number=0,
            original_prompt=system_prompt,
        )
        db.add(prompt)
        await db.flush()
    prompt.title = data.title
    prompt.material_type = MaterialType.OUTLINE.value
    prompt.edited_prompt = system_prompt
    await db.refresh(prompt)

    return OutlinePromptResponse(
        success=True,
        message="Prompt创建成功",
        prompt_id=prompt.id,
        document_id=document_id,
        project_id=project_id,
        system_prompt=system_prompt,
    )


@router.post("/outline/{prompt_id}/generate", response_model=OutlineGenerateResponse)
async def generate_outline_by_prompt(
    prompt_id: str,
    db: AsyncSession = Depends(get_db),
):
    """根据Prompt ID生成大纲。

    Args:
        prompt_id: Prompt ID。
        db: Database session.

    Returns:
        Generated outline with items and metadata.
    """
    # 获取 Prompt
    result = await db.execute(select(Prompt).where(Prompt.id == prompt_id))
    prompt: Prompt | None = result.scalar_one_or_none()
    if prompt is None:
        raise NotFoundException("Prompt not found")
    system_prompt = prompt.edited_prompt or prompt.original_prompt
    if not system_prompt:
        raise BadRequestException("Prompt edited_prompt and original_prompt are both empty")   
    
    project_id = prompt.project_id
    document_id = prompt.document_id

    # 获取 Document
    doc_result = await db.execute(select(Document).where(Document.id == document_id))
    document: Document | None = doc_result.scalar_one_or_none()
    if document is None:
        raise NotFoundException("Document not found")

    # 更新 Document 状态
    document.parse_status = "generating"
    await db.flush()

    service = DeepseekService()
    user_prompt = "按要求生成大纲"

    try:
        result = await service.generate_txt_from_prompt(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            material_type=MaterialType.OUTLINE,
        )
        await _save_sections_to_db(result, document_id, db)
        # 更新 Document 状态
        document.parse_status = "completed"
        await db.flush()
        await db.refresh(document)

        return OutlineGenerateResponse(
            success=True,
            message="大纲生成成功",
            document_id=document_id,
            project_id=project_id,
            duration_ms=result.get("duration_ms", 0),
        )
    except Exception as e:
        document.parse_status = "failed"
        await db.flush()
        await db.refresh(document)
        raise e


@router.post("/outline/generate-direct", response_model=OutlineGenerateResponse)
async def generate_outline_direct(
    data: OutlineGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """使用自定义prompt生成大纲"""
    if not data.outline_prompt:
        raise ValueError("自定义系统prompt不能为空")
    # 1. 获取或创建项目
    project = await _get_project_or_create(data.project_id, db, "直接生成大纲")
    project_id = project.id
    # 2.获取或创建文档
    if data.document_id is not None:
        document = await _get_document(data.document_id, db)
    else:
        # 创建 Document
        document = Document(
            uuid="",
            original_filename="",
            file_type="",
            file_size_bytes=0,
            storage_path=""
        )
        db.add(document)
        await db.flush()

    document.project_id = project_id
    document.title = data.title
    document.parse_status = "generating"
    await db.refresh(document)
    document_id = document.id

    # 3. 获取或创建 Prompt
    if data.prompt_id is not None:
        prompt = await _get_prompt(data.prompt_id, db)
    else:
        prompt = Prompt(
            project_id=project_id,
            document_id=document_id,
            figure_number=0,
            original_prompt="",
        )
        db.add(prompt)
        await db.flush()
    prompt.title = data.title
    prompt.material_type = MaterialType.OUTLINE.value
    prompt.edited_prompt = data.outline_prompt
    await db.refresh(prompt)
    
    service = DeepseekService()
    
    try:
        # 使用自定义prompt作为system_prompt
        result = await service.generate_txt_from_prompt(
            user_prompt="按要求生成大纲",
            system_prompt=data.outline_prompt,
            material_type=MaterialType.OUTLINE,
        )
        await _save_sections_to_db(result, document_id, db)
        document.parse_status = "completed"
        await db.flush()
        await db.refresh(document)
        
        return OutlineGenerateResponse(
            success=True,
            message="大纲生成成功",
            document_id=document_id,
            project_id=project_id,
            duration_ms=result.get("duration_ms", 0),
        )
    except Exception as e:
        document.parse_status = "failed"
        await db.flush()
        await db.refresh(document)
        raise e
