from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.models.color_scheme import ColorScheme
from app.models.document import Document, Section
from app.models.prompt import Prompt
from app.models.project import Project
from app.models.project import Template
from app.schemas.common import MaterialType


async def get_project_from_db(project_id: str, db: AsyncSession) -> Project:
    """Get project by ID, raise NotFoundException if not found or deleted."""
    result = await db.execute(select(Project).where(
        Project.id == project_id, Project.status == "active"))
    project: Project | None = result.scalar_one_or_none()
    if project is None or project.status == "deleted":
        raise NotFoundException("Project not found")
    return project


async def get_project_or_create_from_db(project_id: str | None, db: AsyncSession, project_name: str) -> Project:
    """Get project by ID or create a new one if not found."""
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
    else:
        project = await get_project_from_db(project_id, db)
    return project


async def get_schema_from_db(scheme_id: str, db: AsyncSession) -> ColorScheme:
    """Get color scheme by ID, raise NotFoundException if not found."""
    result = await db.execute(select(ColorScheme).where(ColorScheme.id == scheme_id))
    scheme: ColorScheme | None = result.scalar_one_or_none()
    if scheme is None:
        raise NotFoundException("Color scheme not found")
    return scheme


async def get_document_from_db(document_id: str, db: AsyncSession) -> Document:
    """Get document by ID, raise NotFoundException if not found."""
    result = await db.execute(
        select(Document)
        .where(Document.id == document_id)
    )
    document: Document | None = result.scalar_one_or_none()
    if document is None:
        raise NotFoundException("Document not found")
    return document

async def get_document_without_outline(document_id: str, db: AsyncSession) -> Document:
    """Get document by ID, or create a new one if not found or has no outline.

    - Document exists with sections → return as-is.
    - Document exists without sections → set parse_status='pending' and return.
    - Document not found or no document_id → create a new empty document.
    """
    if document_id:
        try:
            document = await get_document_from_db(document_id, db)
        except NotFoundException:
            # 文档不存在，转到创建新文档
            document = None
    else:
        section_count = (await db.execute(
            select(func.count()).select_from(Section).where(
            Section.document_id == document_id)
        )).scalar_one()
        if not section_count and section_count == 0:
            # 文档存在但无 section，需要重新生成
            document.parse_status = "pending"
            await db.flush()
            return document

    # 无 document_id 或文档不存在，创建一个新的空文档
    document = Document(
        project_id="",
        uuid="",
        original_filename="",
        file_type="",
        file_size_bytes=0,
        storage_path=""
    )
    db.add(document)
    await db.commit()
    return document


async def get_template_from_db(template_id: str, db: AsyncSession) -> Template:
    """Get template by ID, raise NotFoundException if not found."""
    result = await db.execute(select(Template).where(Template.id == template_id))
    template: Template | None = result.scalar_one_or_none()
    if template is None:
        raise NotFoundException("Template not found")
    return template


async def get_prompt_from_db(prompt_id: str, db: AsyncSession) -> Prompt:
    """Get prompt by ID, raise NotFoundException if not found."""
    result = await db.execute(select(Prompt).where(Prompt.id == prompt_id))
    prompt: Prompt | None = result.scalar_one_or_none()
    if prompt is None:
        raise NotFoundException("Prompt not found")
    return prompt


async def get_section_from_db(section_id: int, db: AsyncSession) -> Section:
    """Get section by ID, raise NotFoundException if not found."""
    result = await db.execute(select(Section).where(Section.id == section_id))
    section: Section | None = result.scalar_one_or_none()
    if section is None:
        raise NotFoundException("Section not found")
    return section


async def get_sections_from_db(
    document_id: str, material_type: MaterialType, db: AsyncSession, filters: list = []
) -> list[Section]:
    """Get sections by document ID and material type."""
    _filters = [Section.document_id == document_id, *filters]
    if material_type:
        if material_type == MaterialType.OUTLINE:
            _filters.append(Section.material_type.in_([
                MaterialType.OUTLINE.value, MaterialType.SECTION.value]))
        else:
            _filters.append(Section.material_type == material_type.value)
    result = await db.execute(select(Section).where(*_filters).order_by(Section.order_index.asc()))
    _sections = result.scalars().all()
    return _sections
