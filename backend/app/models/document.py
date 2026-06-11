"""Document model — personal-use version (no user_id)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, new_uuid

if TYPE_CHECKING:
    from .project import Project


class Section(Base, TimestampMixin):
    """Section model representing a chapter/section of a document."""
    __tablename__ = "sections"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    content: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    page_start: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    page_end: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    order_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="sections")


class Document(Base, TimestampMixin):
    """Document model representing an uploaded document."""
    __tablename__ = "documents"

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
    original_filename: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    file_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="docx/txt",
    )
    file_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    storage_path: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )
    page_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    parse_status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
        comment="pending/parsing/completed/failed",
    )
    parse_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="documents")
    sections: Mapped[list["Section"]] = relationship(
        "Section",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="Section.order_index",
    )
