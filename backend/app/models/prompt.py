"""Prompt model — personal-use version (no user_id)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Integer, JSON, String, Text
from app.schemas.document import MaterialType
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, new_uuid

if TYPE_CHECKING:
    from .document import Document
    from .image import Image
    from .project import Project


class Prompt(Base):
    __tablename__ = "prompts"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_uuid,
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    figure_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    title: Mapped[Optional[str]] = mapped_column(
        String(300),
        nullable=True,
    )
    original_prompt: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="AI-generated prompt",
    )
    edited_prompt: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="User-edited prompt",
    )
    suggested_figure_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    suggested_aspect_ratio: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
    )
    source_sections: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Which document sections this prompt covers",
    )
    claude_model: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    material_type: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=MaterialType.OUTLINE.value,
        comment="Material type: 1=outline, 2=references, 3=abstract, 4=acknowledgement, 5=section, 6=figure, 7=table, 8=formula, 9=code",
    )
    generation_status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
    )

    @hybrid_property
    def active_prompt(self) -> Optional[str]:
        """Returns edited_prompt if set, otherwise original_prompt."""
        if self.edited_prompt:
            return self.edited_prompt
        return self.original_prompt

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="prompts")
    document: Mapped[Optional["Document"]] = relationship("Document")
    images: Mapped[list["Image"]] = relationship(
        "Image", back_populates="prompt", cascade="all, delete-orphan"
    )
