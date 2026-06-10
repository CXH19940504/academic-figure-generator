"""Document parsing service for DOCX and TXT files."""

from __future__ import annotations

import io
import logging
import re
from pathlib import PurePosixPath

from docx import Document as DocxDocument

from app.config import get_settings
from app.core.exceptions import FileValidationException

logger = logging.getLogger(__name__)

# Supported extensions mapped to canonical type strings
_EXTENSION_MAP: dict[str, str] = {
    ".docx": "docx",
    ".txt": "txt",
}

# Magic-byte signatures for binary formats
_MAGIC_BYTES: dict[str, bytes] = {
    "docx": b"PK\x03\x04",  # ZIP (Office Open XML)
}


class DocumentService:
    """Parse DOCX and TXT files into structured sections."""

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_file(
        self, filename: str, content: bytes, file_size: int
    ) -> str:
        """Validate a file and return its detected type string.

        Checks:
        1. File extension is among the supported types.
        2. File size does not exceed the configured maximum.
        3. Magic bytes match the claimed extension (for binary types).

        Returns
        -------
        str
            ``"docx"``

        Raises
        ------
        FileValidationException
            When any validation check fails.
        """
        settings = get_settings()
        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024

        # --- extension check ---
        suffix = PurePosixPath(filename).suffix.lower()
        file_type = _EXTENSION_MAP.get(suffix)
        if file_type is None:
            allowed = ", ".join(sorted(_EXTENSION_MAP.keys()))
            raise FileValidationException(
                f"Unsupported file extension '{suffix}'. Allowed: {allowed}"
            )

        # --- size check ---
        if file_size > max_bytes:
            raise FileValidationException(
                f"File size ({file_size / 1024 / 1024:.1f} MB) exceeds the "
                f"maximum allowed ({settings.MAX_UPLOAD_SIZE_MB} MB)"
            )

        # --- magic bytes check (binary formats only) ---
        expected_magic = _MAGIC_BYTES.get(file_type)
        if expected_magic is not None:
            if not content[: len(expected_magic)] == expected_magic:
                raise FileValidationException(
                    f"File content does not match the expected format for "
                    f"'{suffix}' (magic bytes mismatch)"
                )

        return file_type

    # ------------------------------------------------------------------
    # DOCX parsing
    # ------------------------------------------------------------------

    def parse_docx(self, content: bytes) -> dict:
        """Parse a DOCX file using python-docx.

        Uses Word heading styles (``Heading 1``, ``Heading 2``, etc.) to
        identify section structure.

        Returns
        -------
        dict
            ``{"full_text": str, "sections": list[dict], "page_count": None}``
        """
        doc = DocxDocument(io.BytesIO(content))

        sections: list[dict] = []
        current_section: dict | None = None
        full_text_parts: list[str] = []

        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue

            full_text_parts.append(text)
            style_name = para.style.name if para.style else ""

            # Detect heading paragraphs
            is_heading = False
            heading_level = 1

            if style_name.startswith("Heading"):
                is_heading = True
                # Extract level number: "Heading 1" -> 1, "Heading 2" -> 2, etc.
                level_str = style_name.replace("Heading", "").strip()
                try:
                    heading_level = int(level_str) if level_str else 1
                except ValueError:
                    heading_level = 1
            elif style_name == "Title":
                is_heading = True
                heading_level = 1

            if is_heading:
                # Close previous section
                if current_section is not None:
                    current_section["content"] = current_section["content"].strip()
                    sections.append(current_section)

                current_section = {
                    "title": text,
                    "level": heading_level,
                    "content": "",
                    "page_start": None,
                    "page_end": None,
                }
            else:
                if current_section is None:
                    current_section = {
                        "title": "Untitled Section",
                        "level": 1,
                        "content": "",
                        "page_start": None,
                        "page_end": None,
                    }
                current_section["content"] += text + "\n"

        # Flush last section
        if current_section is not None:
            current_section["content"] = current_section["content"].strip()
            sections.append(current_section)

        full_text = "\n".join(full_text_parts)

        return {
            "full_text": full_text,
            "sections": sections,
            "page_count": None,
        }

    # ------------------------------------------------------------------
    # TXT parsing
    # ------------------------------------------------------------------

    def parse_txt(self, content: bytes) -> dict:
        """Parse a TXT file with markdown-style headings.

        Detects headings using:
        - Markdown-style: # Heading 1, ## Heading 2, etc.
        - Or splits by double newlines into sections

        Returns
        -------
        dict
            ``{"full_text": str, "sections": list[dict], "page_count": None}``
        """
        # Try multiple encodings
        text = ""
        for encoding in ["utf-8", "gbk", "gb2312", "utf-16"]:
            try:
                text = content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue

        if not text:
            logger.warning("Failed to decode TXT file with any encoding")
            text = content.decode("utf-8", errors="replace")

        # Normalize newlines
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        sections: list[dict] = []

        # Look for markdown-style headings
        heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
        headings = list(heading_pattern.finditer(text))

        if headings:
            for i, match in enumerate(headings):
                level = len(match.group(1))
                title = match.group(2).strip()
                start = match.end()
                end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
                section_content = text[start:end].strip()

                # Capture any preamble text before the first heading
                if i == 0 and match.start() > 0:
                    preamble = text[: match.start()].strip()
                    if preamble:
                        sections.append(
                            {
                                "title": "摘要 / Preamble",
                                "level": 1,
                                "content": preamble,
                                "page_start": None,
                                "page_end": None,
                            }
                        )

                sections.append(
                    {
                        "title": title,
                        "level": level,
                        "content": section_content,
                        "page_start": None,
                        "page_end": None,
                    }
                )
        else:
            # No headings found – split by double newlines into paragraphs
            blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
            chunk_size = max(1, len(blocks) // 10) if len(blocks) > 10 else 1
            for i in range(0, len(blocks), chunk_size):
                chunk = blocks[i : i + chunk_size]
                combined = "\n\n".join(chunk)
                first_line = chunk[0].split("\n")[0][:80]
                sections.append(
                    {
                        "title": first_line if len(blocks) > 1 else "全文",
                        "level": 1,
                        "content": combined,
                        "page_start": None,
                        "page_end": None,
                    }
                )

        return {
            "full_text": text,
            "sections": sections,
            "page_count": None,
        }

    # ------------------------------------------------------------------
    # Unified parse entry point
    # ------------------------------------------------------------------

    def parse(self, content: bytes, file_type: str) -> dict:
        """Route to the appropriate parser based on file type.

        Parameters
        ----------
        content:
            Raw file bytes.
        file_type:
            ``"docx"`` or ``"txt"``

        Returns
        -------
        dict
            ``{"full_text": str, "sections": list[dict], "page_count": None}``
        """
        parsers = {
            "docx": self.parse_docx,
            "txt": self.parse_txt,
        }

        parser = parsers.get(file_type)
        if parser is None:
            raise FileValidationException(f"No parser available for type '{file_type}'")

        try:
            result = parser(content)
        except FileValidationException:
            raise
        except Exception as exc:
            logger.exception("Failed to parse %s document", file_type)
            raise FileValidationException(
                f"Failed to parse {file_type} document: {exc}"
            ) from exc

        logger.info(
            "Parsed %s document: %d sections, %d chars",
            file_type,
            len(result.get("sections", [])),
            len(result.get("full_text", "")),
        )
        return result
