"""Unit test for outline generation via DeepseekService.

Uses sys.modules stubs to bypass heavy dependencies (PyMuPDF, SQLAlchemy, etc.)
so the test can run with a minimal virtualenv (httpx + fastapi + pydantic-settings).

Usage:
    cd backend
    DEEPSEEK_API_KEY=xxx DEEPSEEK_API_BASE=https://api.deepseek.com \\
        DEEPSEEK_MODEL=deepseek-chat PYTHONPATH=. \\
        .venv-test/bin/python tests/test_outline_prompt.py
"""
import asyncio
import sys
import types

# --- Stub heavy modules BEFORE importing from app ---
# fitz (PyMuPDF) — needed by app.services.document_service
sys.modules.setdefault("fitz", types.ModuleType("fitz"))

# app.services.document_service — needs fitz, python-docx, etc.
_doc_stub = types.ModuleType("app.services.document_service")
_doc_stub.DocumentService = type("DocumentService", (), {})
sys.modules.setdefault("app.services.document_service", _doc_stub)

# app.services.prompt_service — needs sqlalchemy
_prompt_stub = types.ModuleType("app.services.prompt_service")
_prompt_stub.PromptService = type("PromptService", (), {})
sys.modules.setdefault("app.services.prompt_service", _prompt_stub)

# --- Now safe to import ---
from app.services.deepseek_service import DeepseekService
from app.schemas.common import MaterialType
from app.core.prompts.system_prompt import OUTLINE_SYSTEM_PROMPT


async def main():
    service = DeepseekService()
    outline_prompt = (
        OUTLINE_SYSTEM_PROMPT[0]
        .replace("{% major_name %}", "计算机科学与技术")
        .replace("{% word_count %}", "1000")
        .replace("{% paper_type %}", "本科毕业论文")
    )
    result = await service.generate_txt_from_prompt(
        user_prompt="企业考勤管理系统的设计与实现",
        system_prompt=outline_prompt,
        material_type=MaterialType.OUTLINE,
        stream=False,
    )

    items = result["data"]
    print("===== Parsed outline ({} items) =====".format(len(items)))
    for it in items:
        indent = "  " * (it["level"] if it["level"] > 0 else 0)
        extra = "  [mt={}]".format(it.get("material_type")) if it["level"] == 1 else ""
        print("{ind}L{lv} #{ord:02d} {t}{e}".format(
            ind=indent, lv=it["level"], ord=it["order"], t=it["title"][:60], e=extra
        ))


if __name__ == "__main__":
    asyncio.run(main())
