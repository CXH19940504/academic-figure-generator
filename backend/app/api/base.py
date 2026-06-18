from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundException
from app.models.color_scheme import ColorScheme
from app.models.document import Document, Section
from app.models.prompt import Prompt
from app.models.project import Project
from app.models.project import Template
from app.schemas.common import MaterialType


async def get_project_from_db(project_id: str, db: AsyncSession) -> Project:
    """Get project by ID, raise NotFoundException if not found or deleted."""
    result = await db.execute(select(Project).where(Project.id == project_id))
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
        project_id = project.id
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
        .options(selectinload(Document.sections))
    )
    document: Document | None = result.scalar_one_or_none()
    if document is None:
        raise NotFoundException("Document not found")
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


async def get_materials_from_db(
    document_id: str, material_type: MaterialType, db: AsyncSession
) -> list[Section]:
    """Get materials by document ID and material type."""
    result = await db.execute(select(Section).where(
        Section.document_id == document_id,
        Section.material_type == material_type.value
    ))
    materials = result.scalars().all()
    return materials
