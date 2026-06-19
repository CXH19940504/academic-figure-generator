"""Prompt management service — personal-use version (no user_id)."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.models.prompt import Prompt
from app.schemas.common import MaterialType

logger = logging.getLogger(__name__)


class PromptService:
    """CRUD and status queries for AI-generated figure prompts."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_prompts_by_project(self, project_id: str) -> list[Prompt]:
        """Return all prompts belonging to a project, ordered by figure_number."""
        stmt = (
            select(Prompt)
            .where(Prompt.project_id == project_id)
            .order_by(Prompt.figure_number)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_prompt(self, prompt_id: str) -> Prompt:
        """Fetch a single prompt by ID."""
        stmt = select(Prompt).where(Prompt.id == prompt_id)
        result = await self.db.execute(stmt)
        prompt: Prompt | None = result.scalar_one_or_none()
        if prompt is None:
            raise NotFoundException(f"Prompt {prompt_id} not found")
        return prompt

    async def update_prompt(self, prompt_id: str, edited_prompt: str) -> Prompt:
        """Update the edited_prompt field."""
        prompt = await self.get_prompt(prompt_id)
        prompt.edited_prompt = edited_prompt
        await self.db.flush()
        await self.db.refresh(prompt)
        logger.info("Prompt %s updated (edited_prompt length=%d)", prompt_id, len(edited_prompt))
        return prompt

    async def create_prompts_from_figures(
        self,
        project_id: str,
        document_id: str | None,
        figures: list[dict],
        claude_model: str | None = None,
    ) -> list[Prompt]:
        """Create Prompt records from a list of generated figure dicts."""
        prompts: list[Prompt] = []
        for fig in figures:
            prompt = Prompt(
                project_id=project_id,
                document_id=document_id,
                material_type=MaterialType.FIGURE.value,
                figure_number=fig.get("figure_number", len(prompts) + 1),
                title=fig.get("title"),
                original_prompt=fig.get("prompt"),
                suggested_figure_type=fig.get("suggested_figure_type"),
                suggested_aspect_ratio=fig.get("suggested_aspect_ratio"),
                source_sections={
                    "titles": fig.get("source_section_titles", []),
                    "rationale": fig.get("rationale", ""),
                },
                claude_model=claude_model,
                generation_status="completed",
            )
            self.db.add(prompt)
            prompts.append(prompt)

        await self.db.flush()
        for p in prompts:
            await self.db.refresh(p)

        logger.info("Created %d prompts for project %s", len(prompts), project_id)
        return prompts
