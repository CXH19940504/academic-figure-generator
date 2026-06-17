"""Document upload and retrieval endpoints — personal-use (no auth, local storage)."""

import asyncio
import logging

from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.base import get_document_from_db, get_project_from_db, get_project_or_create_from_db, get_prompt_from_db, get_template_from_db
from app.core.exceptions import BadRequestException, NotFoundException
from app.dependencies import get_db
from app.models.document import Document, Section
from app.models.prompt import Prompt
from app.schemas import get_subject_name_by_code
from app.schemas.common import MaterialType, PaperType
from app.schemas.document import (
    DocumentCreate, DocumentResponse, OutlineGenerateRequest, OutlineGenerateResponse,
    OutlinePromptCreateRequest, OutlinePromptResponse, SectionGenerateRequest, SectionGenerateResponse,
    SectionPromptRequest, SectionPromptResponse, SectionsResponse
)
from app.services.local_storage_service import LocalStorageService
from app.services.deepseek_service import DeepseekService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["Documents"])


@router.get("/projects/{project_id}/documents", response_model=list[DocumentResponse])
async def list_project_documents(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    await get_project_from_db(project_id, db)
    result = await db.execute(
        select(Document)
        .where(Document.project_id == project_id)
        .order_by(Document.created_at.desc())
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
    project = await get_project_from_db(project_id, db)

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

    prompt = Prompt(
        project_id=project_id,
        document_id=document.id,
        figure_number=0,
        original_prompt="parsed from file",
        title=document.title,
        material_type=MaterialType.OUTLINE.value,
        generation_status="completed",
    )
    db.add(prompt)
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
    )
    document: Document | None = result.scalar_one_or_none()
    if document is None:
        raise NotFoundException("Document not found")
    return DocumentResponse.model_validate(document)


@router.get("/documents/{document_id}/sections", response_model=SectionsResponse)
async def get_document_sections(
    document_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Section)
        .where(Section.document_id == document_id)
        .order_by(Section.order_index.asc())
    )
    sections: list[Section] = result.scalars().all()
    return SectionsResponse(document_id=document_id, sections=sections)



def _build_system_prompt(skill_name: str, params: dict) -> str:
    """构建大纲生成的 system prompt"""
    service = DeepseekService()
    system_prompt = service._get_skill_content(skill_name)
    for key, value in params.items():
        system_prompt = system_prompt.replace("{% " + key + " %}", str(value or ""))
    return system_prompt

def _build_section_content(sections: list[Section]) -> str:
    """构建章节内容"""
    content = ""
    for section in sections:
        title = section.title or ""
        level = section.level
        content += f"<heading{level}>{title}</heading{level}>\n"
    content += "<section>{% section_content %}</section>"
    return content


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
    project = await get_project_or_create_from_db(data.project_id, db, "直接生成大纲")
    project_id = project.id

    # 2. 获取模板
    if data.template_id is not None:
        template = await get_template_from_db(data.template_id, db)
    else:
        raise BadRequestException("template_id is required")
    template_content = template.content

    # 3.获取或创建文档
    document = Document(uuid="", storage_path="")
    if data.document_id:
        section_count = (await db.execute(select(func.count()).select_from(Section).where(Section.document_id == data.document_id))).scalar_one()
        if section_count is not None and section_count > 0:
            document = await get_document_from_db(data.document_id, db)
    document.project_id = project_id
    document.title = data.title
    document.paper_type = data.paper_type
    document.subject_code = data.subject_code
    document.template_id = data.template_id
    document.original_filename = template.storage_path.split("/")[-1]
    document.file_type = template.storage_path.split(".")[-1]
    document.file_size_bytes = data.word_count
    document.parse_status = "generating"
    if not document.id:
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
    system_prompt = _build_system_prompt(MaterialType.OUTLINE.name, params)

    # 5. 获取或创建 Prompt
    if data.prompt_id:
        prompt = await get_prompt_from_db(data.prompt_id, db)
    else:
        prompt = Prompt(
            project_id=project_id,
            figure_number=0,
            original_prompt=system_prompt,
        )
        db.add(prompt)
        await db.flush()
    prompt.document_id = document_id
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
        section_count = await _save_sections_to_db(result, document_id, db)
        # 更新 Document 状态
        prompt.generation_status = "completed"
        document.parse_status = "completed"
        await db.flush()
        await db.refresh(prompt)
        await db.refresh(document)

        return OutlineGenerateResponse(
            success=True,
            message="大纲生成成功",
            data={'section_count': section_count},
            document_id=document_id,
            project_id=project_id,
            duration_ms=result.get("duration_ms", 0),
        )
    except Exception as e:
        prompt.generation_status = "failed"
        document.parse_status = "failed"
        await db.flush()
        await db.refresh(prompt)
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
    project = await get_project_or_create_from_db(data.project_id, db, "直接生成大纲") 
    project_id = project.id

    # 2.获取或创建文档
    document = Document(
        uuid="",
        original_filename="",
        file_type="",
        file_size_bytes=0,
        storage_path=""
    )
    if data.document_id:
        section_count = (await db.execute(select(func.count()).select_from(Section).where(Section.document_id == data.document_id))).scalar_one()
        if section_count is not None and section_count > 0:
            document = await get_document_from_db(data.document_id, db)
    if document.id is None:
        db.add(document)
        await db.flush()

    document.project_id = project_id
    document.title = data.title
    document.parse_status = "generating"
    await db.refresh(document)
    document_id = document.id

    # 3. 获取或创建 Prompt
    if data.prompt_id:
        prompt = await get_prompt_from_db(data.prompt_id, db)
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
        section_count = await _save_sections_to_db(result, document_id, db)
        prompt.generation_status = "completed"
        document.parse_status = "completed"
        await db.flush()
        await db.refresh(prompt)
        await db.refresh(document)
        
        return OutlineGenerateResponse(
            success=True,
            message="大纲生成成功",
            data={'section_count': section_count},
            document_id=document_id,
            project_id=project_id,
            duration_ms=result.get("duration_ms", 0),
        )
    except Exception as e:
        prompt.generation_status = "failed"
        document.parse_status = "failed"
        await db.flush()
        await db.refresh(prompt)
        await db.refresh(document)
        raise e


@router.post("/projects/{project_id}/sections/prompt", response_model=SectionPromptResponse)
async def create_sections_prompt(
    project_id: str,
    data: SectionPromptRequest,
    db: AsyncSession = Depends(get_db),
):
    """创建章节正文的Prompt并插入数据库。

    Args:
        project_id: Project ID.
        data: Request body with document ID and section indices.
        db: Database session.

    Returns:
        Created prompt with ID and system prompt.
    """
    # 1. 验证项目是否存在
    await get_project_from_db(project_id, db)

    # 2. 获取 Document
    document = await get_document_from_db(data.document_id, db)
    logger.info("create_sections_prompt: document_id=%s, sections_count=%d, subject_code=%s",
                document.id, len(document.sections), document.subject_code)
    if document.project_id != project_id:
        raise BadRequestException("Document does not belong to this project")
    document.parse_status = "generating"
    await db.refresh(document)

    # 3. 合并所有子章节
    update_paragraphs = []
    paragraph: list[Section] = []
    for idx in data.section_indices:
        section = document.sections[idx]
        logger.debug("create_sections_prompt: processing section idx=%d, title=%s, level=%d, material_type=%d",
                     idx, section.title, section.level, section.material_type)
        if not paragraph or section.level >= paragraph[-1].level:
            paragraph.append(section)
        else:
            update_paragraphs.append(paragraph.copy())
            paragraph.clear()
            paragraph.append(section)
    if paragraph:
        update_paragraphs.append(paragraph)
    logger.info("create_sections_prompt: built %d paragraphs from %d sections",
                len(update_paragraphs), len(data.section_indices))

    # 4. 构建 prompt
    exist_cnt_result = await db.execute(
        select(func.count())
        .select_from(Prompt)
        .where(
            Prompt.document_id == document.id,
            Prompt.material_type != MaterialType.FIGURE.value,
        )
    )
    exist_cnt = exist_cnt_result.scalar_one()
    prompt_prompts = {}
    params = {
        "major_name": get_subject_name_by_code(document.subject_code or "08")
    }
    for i, paragraph in enumerate(update_paragraphs):
        try:
            material_type = MaterialType[paragraph[0].material_type]
        except KeyError:
            material_type = MaterialType.SECTION
        logger.info("create_sections_prompt: paragraph[%d] head_section=%s, material_type=%s, section_count=%d",
                    i, paragraph[0].title, material_type.name, len(paragraph))
        system_prompt = _build_system_prompt(material_type.name, params)
        # 合并相同层级的章节
        user_prompt = _build_section_content(paragraph)
        logger.debug("create_sections_prompt: paragraph[%d] system_prompt_len=%d, user_prompt_len=%d",
                     i, len(system_prompt), len(user_prompt))
        prompt_title = paragraph[0].title
        prompt = Prompt(
            title=prompt_title,
            material_type=material_type.value,
            project_id=project_id,
            document_id=document.id,
            figure_number=exist_cnt+i,
            original_prompt=system_prompt+"\nUser Input:"+user_prompt,
            edited_prompt="",
            generation_status="pending",
            source_sections=[section.id for section in paragraph],
        )
        db.add(prompt)
        await db.flush()
        prompt_prompts[prompt.id] = prompt.original_prompt
        logger.info("create_sections_prompt: created prompt id=%s, title=%s, material_type=%s, source_sections=%s",
                    prompt.id, prompt.title, prompt.material_type, prompt.source_sections)

    logger.info("create_sections_prompt: done, created %d prompts for document_id=%s",
                len(prompt_prompts), document.id)

    return SectionPromptResponse(
        success=True,
        message="Prompt创建成功",
        prompt_prompts=prompt_prompts,
        document_id=document.id,
        project_id=project_id,
    )


async def _generate_sections(prompt_id: str, service: DeepseekService):
    """根据prompt_id生成正文（使用独立 DB session，支持并发）"""
    from app.dependencies import get_async_session_factory

    session_factory = get_async_session_factory()
    async with session_factory() as db:
        # 获取 Prompt
        prompt = await get_prompt_from_db(prompt_id, db)
        try:
            prompt_text = prompt.edited_prompt or prompt.original_prompt
            prompt_str = prompt_text.split("\nUser Input:")
            system_prompt, user_prompt = prompt_str[0].strip(), prompt_str[1].strip()
            result = await service.generate_txt_from_prompt(
                user_prompt=user_prompt,
                system_prompt=system_prompt,
                material_type=prompt.material_type,
            )
            section_count = await _save_sections_to_db(result, prompt.document_id, db)
            sections = result.get("data", [])
            for idx, section_id in enumerate(prompt.source_sections):
                await db.execute(update(Section).values(
                    title=sections[idx]["title"],
                    content=sections[idx]["content"],
                ).where(Section.id == section_id))
            # 更新 Prompt 状态
            prompt.generation_status = "completed"
            await db.commit()
            return section_count
        except Exception as e:
            prompt.generation_status = "failed"
            await db.commit()
            raise e


@router.post("/sections/generate", response_model=SectionGenerateResponse)
async def generate_sections_content(
    data: SectionGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """根据Prompt ID生成章节正文内容。

    Args:
        data: Request body with generation parameters.
            document_id: Document ID.
            prompt_ids: Prompt IDs.
        db: Database session.

    Returns:
        Updated sections with generated content.
    """
    # prompt_ids 不能为空
    if not data.prompt_ids:
        raise BadRequestException("prompt_ids is empty")
        
    # 获取 Document
    document: Document = await get_document_from_db(data.document_id, db)

    # 调用 API（每个任务使用独立 DB session，支持并发）
    service = DeepseekService()
    create_tasks = []
    for prompt_id in data.prompt_ids:
        create_tasks.append(asyncio.create_task(
            _generate_sections(prompt_id, service)))
    section_counts = await asyncio.gather(*create_tasks)

    # 更新 Document 状态
    document.parse_status = "completed"
    await db.flush()

    return SectionGenerateResponse(
        success=True,
        message="Sections generated successfully",
        section_count=sum(section_counts),
    )
