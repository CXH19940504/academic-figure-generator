"""Deepseek SDK integration for generating academic figure prompts.

Uses Deepseek's OpenAI-compatible API to call their models with the
academic-figure-prompt SKILL.md injected as system_prompt.

Deepseek API reference: https://platform.deepseek.com/api-docs
"""

from __future__ import annotations

import json
import logging
import re
import time
from enum import Enum
from pathlib import Path
from typing import Any

from app.schemas.common import MaterialType
import httpx

from app.config import get_settings
from app.core.exceptions import ExternalAPIException
from app.core.prompts import system_prompt

logger = logging.getLogger(__name__)
settings = get_settings()


# Path to SKILL.md relative to project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


class SystemPromptName(Enum):
    FIGURE_PROMPT = settings.FIGURE_PROMPT_SKILL_NAME
    OUTLINE = "academic-outline-prompt"
    SECTION = "academic-section-prompt"


def _get_prompt_template(material_name: str, lang: str = "中文") -> str:
    """Get the prompt template for the specified material."""
    try:
        template_id = system_prompt.LANGUAGES.index(lang)
        MaterialType[material_name]
        templates = getattr(system_prompt, material_name + "_SYSTEM_PROMPT")
        # 确保索引不越界，当模板列表长度不足时使用最后一个可用的模板
        safe_index = min(template_id, len(templates) - 1)
        return templates[safe_index]
    except (KeyError, AttributeError):
        return system_prompt.SECTION_SYSTEM_PROMPT[0]


class DeepseekService:
    """Integration with Deepseek via OpenAI-compatible API for generating figure prompts."""

    def __init__(self, api_key: str | None = None, api_base_url: str | None = None) -> None:
        self.api_key = api_key or settings.DEEPSEEK_API_KEY
        self.api_base = (api_base_url or settings.DEEPSEEK_API_BASE).rstrip("/")
        self._skills = {}

        if not self.api_key:
            raise ExternalAPIException(
                "Deepseek",
                "No API key configured. Set DEEPSEEK_API_KEY in environment variables.",
            )

    def _get_skill_content(self, skill_name: str) -> str:
        """Get the content of the specified skill."""
        if skill_name not in self._skills:
            self._skills[skill_name] = _get_prompt_template(skill_name)
        
        if not self._skills[skill_name]:
            logger.warning("%s content loaded — prompts may be generic.", skill_name)

        return self._skills[skill_name]

    async def generate_txt_from_prompt(
        self,
        user_prompt: str,
        system_prompt: str,
        material_type: MaterialType,
        stream: bool = True,
        model: str = None,
    ) -> dict:
        """从已有的 prompt 生成文本。

        Parameters
        ----------
        user_prompt:
            User prompt for the API call.
        system_prompt:
            Pre-built system prompt.
        stream:
            Whether to use streaming API. Default is True.
        model:
            Deepseek model to use.

        Returns
        -------
        dict
            ``{"data": list[dict], "duration_ms": int}``
        """
        if model is None:
            model = settings.DEEPSEEK_MODEL

        start_time = time.monotonic()

        try:
            if stream:
                result_text = await self._call_deepseek_api_stream(user_prompt, model, system_prompt)
            else:
                result_text = await self._call_deepseek_api(user_prompt, model, system_prompt)
        except Exception as exc:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Deepseek API error after %d ms: %s", duration_ms, exc)
            raise ExternalAPIException("Deepseek", f"API error: {exc}") from exc

        duration_ms = int((time.monotonic() - start_time) * 1000)
        if material_type == MaterialType.FIGURE:
            logger.info(
                "Deepseek API call completed in %d ms: %d figure items (stream=%s)",
                duration_ms,
                len(result_text),
                stream,
            )
            return {
                "data": result_text,
                "duration_ms": duration_ms,
            }
        elif material_type not in (MaterialType.FIGURE, MaterialType.TABLE, MaterialType.FORMULA, MaterialType.CODE):
            sections = self._parse_sections_response(result_text)
            logger.info(
                "Deepseek API call completed in %d ms: %d sections items (stream=%s)",
                duration_ms,
                len(sections),
                stream,
            )
            return {
                "data": sections,
                "duration_ms": duration_ms,
                "raw_text": result_text,
            }
        else:
            return {
                "data": result_text,
                "duration_ms": duration_ms,
            }

    async def _call_deepseek_api(self, user_prompt: str, model: str, system_prompt: str=None) -> str:
        """Call Deepseek OpenAI-compatible API (non-streaming)."""
        endpoint = f"{self.api_base}/chat/completions"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 8192,
            "stream": False,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(endpoint, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()

        # Extract content from OpenAI-compatible response
        choices = result.get("choices", [])
        if not choices:
            raise ExternalAPIException("Deepseek", "No choices returned in response")

        message = choices[0].get("message", {})
        content = message.get("content", "")

        if not content:
            raise ExternalAPIException("Deepseek", "Empty content in response")

        return content

    async def _call_deepseek_api_stream(self, user_prompt: str, model: str, system_prompt: str=None) -> str:
        """Call Deepseek OpenAI-compatible API with streaming (SSE).

        Handles Server-Sent Events format:
            data: {"choices": [{"delta": {"content": "..."}}]}
            data: [DONE]
        """
        endpoint = f"{self.api_base}/chat/completions"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 8192,
            "stream": True,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }

        content_chunks: list[str] = []

        async with httpx.AsyncClient(timeout=180.0) as client:
            async with client.stream("POST", endpoint, json=payload, headers=headers) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    line = line.strip()

                    # Skip empty lines
                    if not line:
                        continue

                    # Skip non-data lines
                    if not line.startswith("data: "):
                        continue

                    # Check for stream end
                    data = line[6:]  # Remove "data: " prefix
                    if data == "[DONE]":
                        break

                    # Parse JSON payload
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        logger.warning("Failed to parse SSE data: %s", data[:100])
                        continue

                    # Extract content from delta
                    choices = chunk.get("choices", [])
                    if not choices:
                        continue

                    delta = choices[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        content_chunks.append(content)

        if not content_chunks:
            raise ExternalAPIException("Deepseek", "No content received from streaming response")

        return "".join(content_chunks)

    def _clean_response(self, text: str) -> str:
        """
        Clean up the response text by stripping markdown code fences and extra whitespace.

        Args:
            text (str): The raw response text.

        Returns:
            str: The cleaned response text.
        """
        if not text or not text.strip():
            logger.warning("Empty response from Deepseek")
            return ""

        cleaned = text.strip()

        # Strip markdown code fences if present
        if cleaned.startswith("```"):
            first_newline = cleaned.index("\n") if "\n" in cleaned else len(cleaned)
            cleaned = cleaned[first_newline + 1 :]
            if cleaned.rstrip().endswith("```"):
                cleaned = cleaned.rstrip()[:-3].rstrip()

        return cleaned

    def _parse_sections_response(self, text: str) -> list[dict]:
        """
        Extract and validate the JSON array of sections dicts from Deepseek's response.
        使用 <heading1></heading1>、<heading2></heading2> 和 <heading3></heading3> 解析返回结果，提取正文信息
    
        例子：

        <heading1>摘要</heading1>
        <heading1>绪论</heading1>
        <heading2>研究背景与意义</heading2>
        <heading3>行业发展现状</heading3>
        <heading3>研究的必要性</heading3>
        
        Returns:
            list[dict]: A list of outline dicts with keys: level, title, order.
        """
        logger.info("_parse_sections_response input (len=%d):\n%s", len(text), text)
        cleaned = self._clean_response(text)
        
        # 使用正则表达式解析 heading 标签（使用反向引用确保开闭标签一致）
        # 匹配 <heading1>...</heading1>, <heading2>...</heading2>, <heading3>...</heading3>
        section_pattern = re.compile(
            r"<(heading[1-3]|section)>(.*?)</\1>?",
            re.DOTALL
        )

        outline: list[dict] = []
        order = 0

        for match in section_pattern.finditer(cleaned):
            level = int(match.group(1)[-1]) if match.group(1).startswith("heading") else 4  # 1, 2, or 3
            title = match.group(2).strip()
            
            if not title:
                logger.warning("Empty title for heading%d at position %d", level, match.start())
                continue

            order += 1
            outline.append({
                "level": level,
                "title": title,
                "order": order,
            })

        if not outline:
            logger.warning("Could not parse sections from Deepseek response: no heading tags found")
            outline.append({
                "level": 1,
                "title": cleaned,
                "order": 0,
            })
            sections = outline
        else:
            sections = self._validate_sections(outline)
            logger.info("Parsed %d sections items from Deepseek response", len(sections))
        return sections

    @staticmethod
    def _validate_sections(sections: list) -> list[dict]:
        """Validate and normalize the list of sections dicts."""
        valid: list[dict] = []
        for i, section in enumerate(sections):
            if not isinstance(section, dict):
                logger.warning("Skipping non-dict outline at index %d", i)
                continue

            validated: dict[str, Any] = {
                "level": section.get("level", 1),
                "title": re.split(r'[ .、]', section.get("title", f"Section{i + 1}"))[-1],  # 标题去掉序号前缀
                "order": section.get("order", i + 1),
            }
            if not validated["title"]:
                logger.warning("Skipping section %d: empty title", validated["order"])
                continue

            if validated["level"] == 1:
                validated["material_type"] = MaterialType.get_value_by_name(validated["title"])
                
            valid.append(validated)

        return valid

    async def generate_figure_prompts(
        self,
        sections: list[dict],
        color_scheme: dict,
        paper_field: str | None = None,
        figure_types: list[str] | None = None,
        user_request: str | None = None,
        max_figures: int | None = None,
    ) -> dict:
        """Call Claude via Agent SDK to generate figure prompts.

        Returns:
            dict with keys: figures, duration_ms
        """
        user_prompt = self._build_user_message(
            sections=sections,
            color_scheme=color_scheme,
            paper_field=paper_field,
            figure_types=figure_types,
            user_request=user_request,
            max_figures=max_figures,
        )
        system_prompt = self._get_skill_content(MaterialType.FIGURE.name)
        result = await self.generate_txt_from_prompt(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            material_type=MaterialType.FIGURE,
        )
        figures = self._parse_figures_response(result["data"])
        return {
            "figures": figures,
            "duration_ms": result["duration_ms"],
        }

    def _build_user_message(
        self,
        sections: list[dict],
        color_scheme: dict,
        paper_field: str | None,
        figure_types: list[str] | None = None,
        user_request: str | None = None,
        max_figures: int | None = None,
    ) -> str:
        """Build the user message with paper sections and color palette."""
        parts: list[str] = []

        if paper_field:
            parts.append(f"**Academic Field:** {paper_field}\n")

        # Color palette
        parts.append("**Color Palette to Use (Step 2.5 SKIPPED — already selected by user):**")
        color_block = json.dumps(color_scheme, indent=2)
        parts.append(f"```json\n{color_block}\n```")
        parts.append(
            "The color scheme above has been confirmed by the user as their final choice. "
            "DO NOT stop to present color options — proceed directly to Step 3 to generate figure prompts."
        )
        parts.append("")

        # Figure types
        if figure_types:
            parts.append("**Preferred figure types:**")
            for ft in figure_types:
                parts.append(f"  - {ft}")
            parts.append("")

        # User request
        if user_request and user_request.strip():
            parts.append(f"**User Request (highest priority):**\n{user_request.strip()}\n")

        # Max figures
        if max_figures is not None and max_figures > 0:
            parts.append(f"**Generate at most {max_figures} figure prompt(s).**\n")

        # Paper content
        parts.append("--- PAPER SECTIONS ---\n")
        for i, section in enumerate(sections, 1):
            # Handle both dict and ORM object
            if isinstance(section, dict):
                title = section.get("title", f"Section {i}")
                content = section.get("content", section.get("text", ""))
            else:
                title = getattr(section, "title", f"Section {i}")
                content = getattr(section, "content", "") or ""

            # Truncate very long sections
            max_section_chars = 8000
            if len(content) > max_section_chars:
                content = content[:max_section_chars] + "\n[... section truncated ...]"

            parts.append(f"## Section {i}: {title}")
            parts.append(content)
            parts.append("")

        parts.append("--- END OF PAPER ---\n")
        parts.append(
            "Generate figure prompts that best match the paper content. "
            "Return ONLY valid JSON array. "
            "Each prompt field must be at least 500 words and extremely precise."
        )

        return "\n".join(parts)

    def _parse_figures_response(self, text: str) -> list[dict]:
        """Extract and validate the JSON array of figure dicts from Claude's response."""
        if not text or not text.strip():
            logger.warning("Empty response from Claude")
            return []

        cleaned = text.strip()

        # Strip markdown code fences if present
        if cleaned.startswith("```"):
            first_newline = cleaned.index("\n") if "\n" in cleaned else len(cleaned)
            cleaned = cleaned[first_newline + 1 :]
            if cleaned.rstrip().endswith("```"):
                cleaned = cleaned.rstrip()[:-3].rstrip()

        # Try direct parse
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, list):
                return self._validate_figures(parsed)
        except json.JSONDecodeError:
            pass

        # Fallback: search for JSON array
        match = re.search(r"\[[\s\S]*\]", cleaned)
        if match:
            try:
                parsed = json.loads(match.group())
                if isinstance(parsed, list):
                    return self._validate_figures(parsed)
            except json.JSONDecodeError:
                pass

        logger.warning("Could not parse JSON figures from Claude response")
        logger.warning("Raw Claude response (first 3000 chars): %s", text[:3000] if text else "(empty)")
        return []

    @staticmethod
    def _validate_figures(figures: list) -> list[dict]:
        """Validate and normalize the list of figure dicts."""
        valid: list[dict] = []
        for i, fig in enumerate(figures):
            if not isinstance(fig, dict):
                logger.warning("Skipping non-dict figure at index %d", i)
                continue

            validated: dict[str, Any] = {
                "figure_number": fig.get("figure_number", i + 1),
                "title": fig.get("title", f"Figure {i + 1}"),
                "suggested_figure_type": fig.get("suggested_figure_type", fig.get("figure_type", "diagram")),
                "suggested_aspect_ratio": fig.get("suggested_aspect_ratio", "16:9"),
                "prompt": fig.get("prompt", ""),
            }

            if not validated["prompt"]:
                logger.warning("Skipping figure %d: empty prompt", validated["figure_number"])
                continue

            valid.append(validated)

        return valid
