"""Project model — personal-use version (no user_id)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, new_uuid

if TYPE_CHECKING:
    from .document import Document
    from .image import Image
    from .prompt import Prompt


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_uuid,
    )
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    paper_field: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="e.g. 'computer vision', 'NLP'",
    )
    color_scheme: Mapped[str] = mapped_column(
        String(50),
        default="okabe-ito",
        nullable=False,
    )
    custom_colors: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="active",
        nullable=False,
        comment="active/archived/deleted",
    )

    # Relationships
    documents: Mapped[list["Document"]] = relationship(
        "Document", back_populates="project", cascade="all, delete-orphan"
    )
    prompts: Mapped[list["Prompt"]] = relationship(
        "Prompt", back_populates="project", cascade="all, delete-orphan"
    )
    images: Mapped[list["Image"]] = relationship(
        "Image", back_populates="project", cascade="all, delete-orphan"
    )
    templates: Mapped[list["Template"]] = relationship(
        "Template", back_populates="project", cascade="all, delete-orphan"
    )



class Template(Base, TimestampMixin):
    __tablename__ = "templates"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_uuid,
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="关联的项目ID",
    )
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    content: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    storage_path: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="存储路径",
    )

    # Relationship
    project: Mapped["Project"] = relationship("Project", back_populates="templates")