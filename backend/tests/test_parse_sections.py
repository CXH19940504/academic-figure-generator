"""Test cases for _parse_sections_response method in DeepseekService."""
import pytest
from app.services.deepseek_service import DeepseekService, MaterialType


class TestParseSectionsResponse:
    """Test cases for heading tag parsing."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = DeepseekService()

    def test_parse_heading1_only(self):
        """Test parsing with only heading1 tags."""
        text = """
        <heading1>摘要</heading1>
        <heading1>绪论</heading1>
        <heading1>结论</heading1>
        """

        sections = self.service._parse_sections_response(text)

        assert len(sections) == 3
        assert sections[0]["level"] == 1
        assert sections[0]["title"] == "摘要"
        assert sections[1]["title"] == "绪论"
        assert sections[2]["title"] == "结论"

    def test_parse_docstring_example(self):
        """Test parsing with the docstring example (deepseek_service.py L267-271).

        This tests the exact example from the _parse_sections_response docstring.
        """
        text = """<heading1>摘要</heading1>
<heading1>绪论</heading1>
<heading2>研究背景与意义</heading2>
<heading3>行业发展现状</heading3>
<section>这是行业现状现状的详细内容</section>
<heading3>研究的必要性</heading3>"""

        sections = self.service._parse_sections_response(text)

        assert len(sections) == 6
        # Verify each section — <section> tags produce level-4 items, not merged into preceding headings
        assert sections[0] == {"level": 1, "title": "摘要", "order": 1, "material_type": MaterialType.ABSTRACT.value}
        assert sections[1] == {"level": 1, "title": "绪论", "order": 2, "material_type": MaterialType.INTRODUCTION.value}
        assert sections[2] == {"level": 2, "title": "研究背景与意义", "order": 3}
        assert sections[3] == {"level": 3, "title": "行业发展现状", "order": 4}
        assert sections[4] == {"level": 4, "title": "这是行业现状现状的详细内容", "order": 5}
        assert sections[5] == {"level": 3, "title": "研究的必要性", "order": 6}
