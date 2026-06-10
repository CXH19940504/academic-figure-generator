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
from pathlib import Path
from typing import Any

import httpx

from app.config import get_settings
from app.core.exceptions import ExternalAPIException

logger = logging.getLogger(__name__)

# Path to SKILL.md relative to project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_SKILL_PATH = _PROJECT_ROOT / "academic-figure-prompt" / "SKILL.md"


def _load_skill_content() -> str:
    """Load the academic-figure-prompt SKILL.md content."""
    if not _SKILL_PATH.exists():
        logger.warning("SKILL.md not found at %s", _SKILL_PATH)
        return ""
    return _SKILL_PATH.read_text(encoding="utf-8")


class DeepseekService:
    """Integration with Deepseek via OpenAI-compatible API for generating figure prompts."""

    # Deepseek model options
    MODELS = {
        "chat": "deepseek-v4-flash",
        "code": "deepseek-v4-pro",
        "code-v2": "deepseek-code-v2",
        "math": "deepseek-math",
    }

    def __init__(self, api_key: str | None = None, api_base_url: str | None = None) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.DEEPSEEK_API_KEY
        self.api_base = (api_base_url or settings.DEEPSEEK_API_BASE).rstrip("/")
        self.skill_content = _load_skill_content()

        if not self.api_key:
            raise ExternalAPIException(
                "Deepseek",
                "No API key configured. Set DEEPSEEK_API_KEY in environment variables.",
            )

        if not self.skill_content:
            logger.warning("No SKILL.md content loaded — prompts may be generic.")

    async def generate_figure_prompts(
        self,
        sections: list[dict],
        color_scheme: dict,
        paper_field: str | None = None,
        figure_types: list[str] | None = None,
        user_request: str | None = None,
        max_figures: int | None = None,
        model: str = "deepseek-chat",
        stream: bool = True,
    ) -> dict:
        """Call Deepseek via OpenAI-compatible API to generate figure prompts.

        Parameters
        ----------
        sections:
            List of paper sections with title and content.
        color_scheme:
            Color palette dictionary for the figure generation.
        paper_field:
            Academic field/discipline (e.g., 'computer vision', 'NLP').
        figure_types:
            List of preferred figure types.
        user_request:
            Optional user-specific request (highest priority).
        max_figures:
            Maximum number of figure prompts to generate.
        model:
            Deepseek model to use. Default is 'deepseek-chat'.
        stream:
            Whether to use streaming API. Default is True for better latency.

        Returns
        -------
        dict
            ``{"figures": list[dict], "duration_ms": int}``
        """
        user_prompt = self._build_user_message(
            sections=sections,
            color_scheme=color_scheme,
            paper_field=paper_field,
            figure_types=figure_types,
            user_request=user_request,
            max_figures=max_figures,
        )

        start_time = time.monotonic()

        try:
            if stream:
                result_text = await self._call_deepseek_api_stream(user_prompt, model)
            else:
                result_text = await self._call_deepseek_api(user_prompt, model)
        except Exception as exc:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Deepseek API error after %d ms: %s", duration_ms, exc)
            raise ExternalAPIException(
                "Deepseek", f"API error: {exc}"
            ) from exc

        duration_ms = int((time.monotonic() - start_time) * 1000)
        figures = self._parse_figures_response(result_text)

        logger.info(
            "Deepseek API call completed in %d ms: %d figures (stream=%s)",
            duration_ms,
            len(figures),
            stream,
        )

        return {
            "figures": figures,
            "duration_ms": duration_ms,
        }

    async def _call_deepseek_api(self, user_prompt: str, model: str) -> str:
        """Call Deepseek OpenAI-compatible API (non-streaming)."""
        endpoint = f"{self.api_base}/chat/completions"

        messages = [
            {"role": "system", "content": self.skill_content},
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

    async def _call_deepseek_api_stream(self, user_prompt: str, model: str) -> str:
        """Call Deepseek OpenAI-compatible API with streaming (SSE).

        Handles Server-Sent Events format:
            data: {"choices": [{"delta": {"content": "..."}}]}
            data: [DONE]
        """
        endpoint = f"{self.api_base}/chat/completions"

        messages = [
            {"role": "system", "content": self.skill_content},
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
        parts.append("**Color Palette to Use:**")
        color_block = json.dumps(color_scheme, indent=2)
        parts.append(f"```json\n{color_block}\n```")
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
            title = section.get("title", f"Section {i}")
            content = section.get("content", section.get("text", ""))

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
        """Extract and validate the JSON array of figure dicts from Deepseek's response."""
        if not text or not text.strip():
            logger.warning("Empty response from Deepseek")
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

        logger.warning("Could not parse JSON figures from Deepseek response")
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
                "source_section_titles": fig.get("source_section_titles", []),
                "rationale": fig.get("rationale", ""),
            }

            if not validated["prompt"]:
                logger.warning("Skipping figure %d: empty prompt", validated["figure_number"])
                continue

            valid.append(validated)

        return valid
