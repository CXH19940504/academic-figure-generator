from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import MaterialType, PaperMaterials, PaperType


class PaperConfig(BaseModel):
    """论文配置参数"""
    id: int  # 配置ID
    document_id: str  # 论文ID
    degree: str  # 学历层次（大专/本科/硕士/博士/MBA）
    word_count: int  # 字数要求


class SectionInfo(BaseModel):
    """Section schema for API responses."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: str
    title: str
    level: int
    content: Optional[str] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    order_index: int = 0
    insert_table: Optional[str] = None
    insert_image: Optional[str] = None
    insert_formula: Optional[str] = None
    insert_code: Optional[str] = None


class SectionsResponse(BaseModel):
    """Sections schema for API responses."""
    model_config = ConfigDict(from_attributes=True)

    document_id: str
    sections: List[SectionInfo] = []


class DocumentResponse(BaseModel):
    """Document schema for API responses."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    uuid: Optional[str] = None  # 用户ID
    title: Optional[str] = None  # 论文标题
    paper_type: Optional[int] = None  # 论文类型
    subject_code: Optional[str] = None  # 学科代码
    template_id: Optional[str] = None  # 排版模板ID
    original_filename: str
    file_type: str
    file_size_bytes: int
    page_count: Optional[int] = None
    parse_status: str
    parse_error: Optional[str] = None
    created_at: datetime


class DocumentCreate(BaseModel):
    """Document creation schema for API requests."""
    uuid: str = ""  # 用户ID
    title: str  # 论文标题
    paper_type: int  # 论文类型
    subject_code: str  # 学科代码
    template_id: Optional[str] = None  # 排版模板ID


class OutlineGenerateRequest(BaseModel):
    prompt_id: str | None = Field(default=None, description="已有的Prompt ID，用于复用。")
    project_id: str | None = Field(default=None, description="项目ID，用于关联项目模板。")
    document_id: str | None = Field(default=None, description="文档ID，用于关联已有文档。")
    title: str = Field(..., min_length=10, max_length=500, description="论文标题")
    paper_type: int = Field(default=1, ge=1, le=4, description="论文类型：1=毕业论文, 2=期刊论文, 3=实习报告, 4=调查报告")
    subject_code: str = Field(default="08", description="学科代码（参考教育部学科分类）")
    subject_name: str = Field(default="", description="学科名称（参考教育部学科分类）")
    degree: str = Field(default="本科", description="学历层次：大专/本科/硕士/博士/MBA")
    word_count: int = Field(default=15000, ge=5000, le=100000, description="目标字数")
    template_id: str | None = Field(default=None, description="排版模板ID")
    outline_prompt: str = Field(default="", description="自定义系统prompt")


class OutlineGenerateResponse(BaseModel):
    success: bool = True
    message: str = "大纲生成成功"
    data: dict | None = None
    document_id: str = ""
    project_id: str | None = None
    duration_ms: int


class OutlinePromptCreateRequest(BaseModel):
    """创建大纲Prompt的请求"""
    prompt_id: str | None = Field(default=None, description="已有的Prompt ID，用于复用。")
    project_id: str | None = Field(default=None, description="项目ID，用于关联项目模板。")
    document_id: str | None = Field(default=None, description="文档ID，用于关联文档。")
    title: str = Field(..., min_length=10, max_length=500, description="论文标题")
    paper_type: int = Field(default=1, ge=1, le=4, description="论文类型：1=毕业论文, 2=期刊论文, 3=实习报告, 4=调查报告")
    subject_code: str = Field(default="08", description="学科代码（参考教育部学科分类）")
    degree: str = Field(default="本科", description="学历层次：大专/本科/硕士/博士/MBA")
    word_count: int = Field(default=15000, ge=5000, le=100000, description="目标字数")
    template_id: str | None = Field(default=None, description="排版模板ID")


class OutlinePromptResponse(BaseModel):
    """大纲Prompt创建的响应"""
    success: bool = True
    message: str = "Prompt创建成功"
    prompt_id: str
    document_id: str
    project_id: str
    system_prompt: str


class SectionPromptRequest(BaseModel):
    """生成章节Prompt的请求"""
    document_id: str = Field(..., description="Document ID")
    section_indices: list[int] | None = Field(
        default=None, description="Selected section indices")


class SectionPromptResponse(BaseModel):
    """生成章节Prompt的响应"""
    success: bool = True
    message: str = "Prompt创建成功"
    prompt_prompts: dict[str, str] = Field(
        default_factory=dict, description="Created prompt IDs and prompts")
    document_id: str
    project_id: str


class SectionGenerateRequest(BaseModel):
    """生成章节正文的请求"""
    document_id: str = Field(..., description="Document ID")
    prompt_ids: list[str] = Field(..., description="Prompt IDs")


class SectionGenerateResponse(BaseModel):
    """生成章节正文的响应"""
    success: bool = True
    message: str = "Sections generated successfully"
    sections: list[dict] = Field(default_factory=list, description="Updated sections with content")
