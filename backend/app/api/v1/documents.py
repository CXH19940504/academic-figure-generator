"""Document upload and retrieval endpoints — personal-use (no auth, local storage)."""

import asyncio
import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, Form, UploadFile
from sqlalchemy import func, select, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.base import (
    get_document_from_db, get_project_from_db, get_project_or_create_from_db,
    get_prompt_from_db, get_template_from_db,
    get_document_without_outline, get_section_from_db, get_sections_from_db,
   )
from app.core.exceptions import BadRequestException, NotFoundException
from app.dependencies import get_db
from app.models.document import Document, Section
from app.models.prompt import Prompt
from app.schemas import get_subject_name_by_code
from app.schemas.common import MaterialType, PaperType
from app.schemas.document import (
    DocumentCreate, DocumentResponse, OutlineGenerateRequest, OutlineGenerateResponse,
    OutlinePromptCreateRequest, OutlinePromptResponse, SectionGenerateRequest, SectionGenerateResponse,
    SectionPromptRequest, SectionPromptResponse, SectionsResponse, SectionUpdateRequest
)
from app.services.local_storage_service import LocalStorageService
from app.services.deepseek_service import DeepseekService
from app.dependencies import get_async_session_factory

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
    data: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """Upload a document to a project.

    Accepts DOCX or TXT files. The file is stored locally and parsed
    synchronously (inline).
    """
    original_filename = file.filename or "unnamed"
    if data:
        data_obj = DocumentCreate.model_validate_json(data)
    else:
        # Derive sensible defaults from filename when no metadata is provided
        data_obj = DocumentCreate(
            title=os.path.splitext(original_filename)[0],
            paper_type=1,
            subject_code="08",
        )
    project = await get_project_from_db(project_id, db)

    contents = await file.read()
    file_size = len(contents)

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
        uuid=data_obj.uuid,
        title=data_obj.title,
        paper_type=data_obj.paper_type,
        subject_code=data_obj.subject_code,
        template_id=data_obj.template_id,
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
        section_count = await _save_sections_to_db(
            parse_result.get("sections"), document.id, db)
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
    for idx, section in enumerate(sections):
        title = section.title or ""
        level = section.level
        content += f"<heading{level}>{title}</heading{level}>\n"
        if idx == len(sections) - 1 or section.level >= sections[idx + 1].level:
            content += "<section>{% section_content %}</section>\n"
    return content


async def _save_sections_to_db(sections: list[dict], document_id: str, db: AsyncSession) -> int:
    """将大纲数据保存到数据库"""
    logger = logging.getLogger(__name__)
    logger.info("_save_sections_to_db called, sections keys: %s, document_id: %s", list(sections[0].keys() if sections else []), document_id)
    logger.info("_save_sections_to_db: found %d sections", len(sections))

    for idx, section_data in enumerate(sections):
        section = Section(
            document_id=document_id,
            title=section_data.get("title", f"Section {idx + 1}"),
            level=section_data.get("level", 1),
            material_type=section_data.get("material_type", MaterialType.SECTION.value),
            content=section_data.get("content", ""),
            page_start=section_data.get("page_start", None),
            page_end=section_data.get("page_end", None),
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
    if data.document_id:
        section_count = (await db.execute(select(func.count()).select_from(Section).where(Section.document_id == data.document_id))).scalar_one()
        if section_count is None or section_count == 0:
            document = await get_document_from_db(data.document_id, db)
        else:
            document = Document(
                uuid="",
                original_filename="",
                file_type="",
                file_size_bytes=0,
                storage_path="",
            )
    else:
        document = Document(
            uuid="",
            original_filename="",
            file_type="",
            file_size_bytes=0,
            storage_path="",
        )

    # Set all required fields BEFORE any potential flush
    document.project_id = project_id
    document.title = data.title
    document.paper_type = data.paper_type
    document.subject_code = data.subject_code
    document.template_id = data.template_id
    document.original_filename = template.storage_path.split("/")[-1]
    document.file_type = template.storage_path.split(".")[-1]
    document.file_size_bytes = data.word_count
    document.parse_status = "generating"

    if document.id is None:
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

    return OutlinePromptResponse(
        success=True,
        message="Prompt创建成功",
        prompt_id=data.prompt_id,
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
    prompt = await get_prompt_from_db(prompt_id, db)
    system_prompt = prompt.edited_prompt or prompt.original_prompt
    if not system_prompt:
        raise BadRequestException("Prompt edited_prompt and original_prompt are both empty")   
    
    project_id = prompt.project_id
    document_id = prompt.document_id

    # 获取 Document
    document = await get_document_from_db(document_id, db)
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
        document = await get_document_without_outline(document_id, db)
        document_id = document.id
        section_count = await _save_sections_to_db(result.get("data", []), document_id, db)
        # 更新 Document 状态
        prompt.generation_status = "completed"
        document.parse_status = "completed"
        await db.flush()

        return OutlineGenerateResponse(
            success=True,
            message="大纲生成成功",
            data={'section_count': section_count},
            document_id=document_id,
            project_id=project_id,
            prompt_id=prompt_id,
            duration_ms=result.get("duration_ms", 0),
        )
    except Exception as e:
        prompt.generation_status = "failed"
        document.parse_status = "failed"
        await db.flush()
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
    document = await get_document_without_outline(data.document_id, db)
    document.project_id = project_id
    document.title = data.title
    document.parse_status = "generating"
    await db.flush()
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
        await db.refresh(prompt)

    prompt.document_id = document_id
    prompt.title = data.title
    prompt.material_type = MaterialType.OUTLINE.value
    prompt.edited_prompt = data.outline_prompt
    await db.flush()
    await db.commit()  # 持久化 Prompt，避免后续生成失败导致 Prompt 丢失

    service = DeepseekService()
    
    try:
        # 使用自定义prompt作为system_prompt
        result = await service.generate_txt_from_prompt(
            user_prompt="按要求生成大纲",
            system_prompt=data.outline_prompt,
            material_type=MaterialType.OUTLINE,
        )
        document = await get_document_without_outline(document_id, db)
        document_id = document.id
        section_count = await _save_sections_to_db(result.get("data", []), document_id, db)
        prompt.generation_status = "completed"
        document.parse_status = "completed"
        await db.flush()
        
        return OutlineGenerateResponse(
            success=True,
            message="大纲生成成功",
            data={'section_count': section_count},
            document_id=document_id,
            project_id=project_id,
            prompt_id=prompt.id,
            duration_ms=result.get("duration_ms", 0),
        )
    except Exception as e:
        prompt.generation_status = "failed"
        document.parse_status = "failed"
        await db.flush()
        await db.commit()  # 持久化失败状态
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
    if document.project_id != project_id:
        raise BadRequestException("Document does not belong to this project")

    # 3. 合并所有子章节
    if not data.section_indices:
        raise BadRequestException("section_indices must not be empty")
    sections = await get_sections_from_db(
        data.document_id, None, db,
         filters=[Section.id.in_(data.section_indices)])
    if not sections:
        raise BadRequestException("No sections found with the given indices")
    
    update_paragraphs = []
    paragraph: list[Section] = []
    for section in sections:
        if not paragraph or section.level > paragraph[0].level:
            # 获取章节类型
            try:
                MaterialType(section.material_type)
            except KeyError:
                logger.error("create_sections_prompt: title=%s, material_type=%d not found in MaterialType",
                                section.title, section.material_type)
                section.material_type = MaterialType.SECTION.value
        else:
            update_paragraphs.append(paragraph)
            paragraph = list()
        paragraph.append(section)
    if paragraph:
        update_paragraphs.append(paragraph)
    logger.info("create_sections_prompt: built %d paragraphs from %d sections",
                len(update_paragraphs), len(sections))

    # 4. 构建 prompt
    document.parse_status = "generating"
    await db.flush()
    exist_cnt = (await db.execute(
        select(func.count())
        .select_from(Prompt)
        .where(
            Prompt.document_id == document.id,
            Prompt.material_type != MaterialType.FIGURE.value,
        )
    )).scalar_one()
    # 5. 构建 prompt
    prompt_ids = []
    params = {
        "major_name": get_subject_name_by_code(document.subject_code or "08"),
        "paper_title": document.title,
        "paper_type": PaperType.get_name(document.paper_type),
    }
    
    material_types: set[int] = set()
    for paragraph in update_paragraphs:
        material_types.add(paragraph[0].material_type)

    # 预查询 abstract_sections，当存在非 ABSTRACT 的 material_type 时需要注入摘要内容
    has_non_abstract_types = len(material_types - {MaterialType.ABSTRACT.value}) > 0
    if has_non_abstract_types:
        try:
            abstract_sections = await get_sections_from_db(document.id, MaterialType.ABSTRACT, db)
            if abstract_sections:
                params["abstract_content"] = abstract_sections[0].content
            else:
                raise BadRequestException("Abstract sections not found")
        except Exception:
            raise BadRequestException("Failed to fetch abstract sections")

    if {MaterialType.ABSTRACT.value, MaterialType.INTRODUCTION.value, MaterialType.CONCLUSION.value} & material_types:
        headers_sections =  await get_sections_from_db(document.id, MaterialType.OUTLINE, db)
        if not headers_sections:
            raise BadRequestException("Document does not generate headers")
        params["all_titles"] = '\n'.join(["#"*section.level + " " + section.title for section in headers_sections])
    
    for i, paragraph in enumerate(update_paragraphs):
        material_type: MaterialType = MaterialType(paragraph[0].material_type)
        logger.info("create_sections_prompt: paragraph[%d] head_section=%s, material_type=%s, section_count=%d",
                    i, paragraph[0].title, material_type.name, len(paragraph))
        # 章节/非章节的user_prompt处理
        if material_type == MaterialType.ABSTRACT:
            user_prompt = params["all_titles"]
        else:
            # 合并相同层级的章节
            user_prompt = _build_section_content(paragraph)
        
        # 构建system_prompt
        system_prompt = _build_system_prompt(material_type.name, params)
        logger.debug("create_sections_prompt: paragraph[%d] system_prompt_len=%d, user_prompt_len=%d",
                     i, len(system_prompt), len(user_prompt))
        prompt = Prompt(
            title=paragraph[0].title,
            material_type=material_type.value,
            project_id=project_id,
            document_id=document.id,
            figure_number=exist_cnt+i,
            original_prompt=system_prompt+"\nUser Input:\n"+user_prompt,
            edited_prompt="",
            generation_status="pending",
            source_sections=[section.id for section in paragraph],
        )
        db.add(prompt)
        await db.flush()
        prompt_ids.append(prompt.id)

    logger.info("create_sections_prompt: done, created %d prompts for document_id=%s",
                len(prompt_ids), document.id)
    
    return SectionPromptResponse(
        success=True,
        message="Prompt创建成功",
        prompt_ids=prompt_ids,
        document_id=document.id,
        project_id=project_id,
    )


async def _generate_abstract(prompt_id: str, section_id: int, section_prompt_ids: list[str]):
    """根据prompt_id生成摘要（使用独立 DB session，支持并发，带数据库锁重试）"""
    abstract_execption = await _generate_sections(prompt_id)
    if abstract_execption or not section_prompt_ids:
        return abstract_execption
    
    session_factory = get_async_session_factory()
    async with session_factory() as db:
        section = await get_section_from_db(section_id, db)
        result = await db.execute(select(Prompt).where(Prompt.id.in_(section_prompt_ids)))
        for _prompt in result.scalars().all():
            _prompt.original_prompt = _prompt.original_prompt.replace(
                "{% abstract_content %}", section.content)
        logger.info("generate_abstract: %s, abstract_section=%d", prompt_id, section.content)
        await db.commit()


async def _generate_sections(prompt_id: str):
    """根据prompt_id生成正文（使用独立 DB session，支持并发，带数据库锁重试）"""

    service = DeepseekService()
    session_factory = get_async_session_factory()

    max_retries = 5
    last_exception = None

    async def _mark_failed():
        """在独立 session 中标记 prompt 为 failed。"""
        try:
            async with session_factory() as fresh_db:
                fresh_prompt = await get_prompt_from_db(prompt_id, fresh_db)
                fresh_prompt.generation_status = "failed"
                await fresh_db.commit()
        except Exception:
            logger.exception("Failed to mark prompt %s as failed", prompt_id)

    for attempt in range(max_retries):
        async with session_factory() as db:
            prompt = await get_prompt_from_db(prompt_id, db)
            section_count = 0
            try:
                prompt_str = (prompt.active_prompt or "").split("\nUser Input:\n")
                if len(prompt_str) != 2:
                    raise BadRequestException("Prompt format error: missing User Input section")
                system_prompt, user_prompt = prompt_str[0].strip(), prompt_str[1].strip()
                result = await service.generate_txt_from_prompt(
                    user_prompt=user_prompt,
                    system_prompt=system_prompt,
                    material_type=prompt.material_type,
                )
                if prompt.material_type == MaterialType.ABSTRACT:
                    sections = result.get("data", [])
                    if not sections:
                        raw_text = result.get("raw_text", "")
                        if not raw_text or not raw_text.strip():
                            raise BadRequestException("Abstract content is empty")
                        logger.warning(
                            "Abstract parsing returned empty, using raw_text as fallback (len=%d)",
                            len(raw_text),
                        )
                        sections = [{"level": 4, "title": raw_text.strip(), "order": 1}]
                    await db.execute(update(Section).where(
                        Section.id == prompt.source_sections[0]
                    ).values(
                        content=sections[0]["title"],
                    ))
                    section_count += 1
                else:
                    input_sections = service._parse_sections_response(user_prompt)
                    sections = result.get("data", [])
                    if not sections:
                        raise BadRequestException("AI 返回格式错误")
                    header_idx = 0
                    input_idx = 0
                    for _section in sections:
                        if _section["level"] > 3:
                            while input_idx < len(input_sections) and input_sections[input_idx]["level"] <= 3:
                                input_idx += 1
                                header_idx += 1
                            input_idx += 1
                            if header_idx < len(prompt.source_sections):
                                await db.execute(update(Section).where(
                                    Section.id == prompt.source_sections[header_idx-1]
                                ).values(
                                    content = _section["title"],
                                ))
                                section_count += 1
                            else:
                                header_idx += 1
                                logger.warning("Exceeded source sections count, skipping section %s", _section["title"])
                        else:
                            input_idx += 1
                            header_idx += 1 
                prompt.generation_status = "completed"
                await db.commit()
                return section_count
            except OperationalError as e:
                await db.rollback()
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    wait = 0.1 * (2 ** attempt)
                    logger.warning(
                        "Database locked for prompt %s, retrying in %.1fs (attempt %d/%d)",
                        prompt_id, wait, attempt + 1, max_retries,
                    )
                    last_exception = e
                    await asyncio.sleep(wait)
                    continue
                await _mark_failed()
                raise
            except Exception:
                await db.rollback()
                await _mark_failed()
                raise

    raise last_exception  # type: ignore[misc]


@router.put("/sections/{section_id}", response_model=dict)
async def update_section(
    section_id: int,
    data: SectionUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """更新指定章节的标题、内容或级别。

    Args:
        section_id: Section ID.
        data: Update data with optional title, content, level.
        db: Database session.

    Returns:
        Success message.
    """
    # 获取现有的 section
    result = await db.execute(select(Section).where(Section.id == section_id))
    section = result.scalar_one_or_none()

    if not section:
        raise NotFoundException(f"Section with id {section_id} not found")

    # 更新字段
    if data.title is not None:
        section.title = data.title
    if data.content is not None:
        section.content = data.content
    if data.level is not None:
        section.level = data.level

    await db.flush()
    await db.refresh(section)

    return {
        "success": True,
        "message": "Section updated successfully",
        "section": {
            "id": section.id,
            "title": section.title,
            "content": section.content,
            "level": section.level,
        }
    }


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

    # 提前提交父 session，释放数据库锁，避免与并发任务冲突
    await db.commit()

    # 调用 API（每个任务使用独立 DB session，支持并发）
    create_tasks = []
    for prompt_id in data.prompt_ids:
        create_tasks.append(asyncio.create_task(
            _generate_sections(prompt_id)))
    # 使用 return_exceptions=True 处理部分失败
    results = await asyncio.gather(*create_tasks, return_exceptions=True)

    # 收集成功/失败统计
    succeeded = 0
    failed = 0
    errors = []
    for r in results:
        if isinstance(r, Exception):
            failed += 1
            errors.append(str(r))
        else:
            succeeded += r

    # 更新 Document 状态（在新事务中）
    document.parse_status = "completed" if failed == 0 else "partial"
    db.add(document)
    await db.flush()
    await db.commit()

    return SectionGenerateResponse(
        success=failed == 0,
        message=f"Sections generated: {succeeded} succeeded, {failed} failed"
                + (f" — errors: {'; '.join(errors[:3])}" if errors else ""),
        section_count=succeeded,
    )
