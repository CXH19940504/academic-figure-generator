from datetime import datetime
from enum import IntEnum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class PaperType(IntEnum):
    """论文类型"""
    GRADUATION = 1  # 毕业论文
    JOURNAL = 2  # 期刊论文
    INTERNSHIP = 3  # 实习报告
    SURVEY = 4  # 调查报告

    @classmethod
    def get_name(cls, value: int) -> str:
        """获取枚举值的名称"""
        names = {
            1: "毕业论文",
            2: "期刊论文",
            3: "实习报告",
            4: "调查报告"
        }
        return names.get(value, "")

    @classmethod
    def get_description(cls, value: int) -> str:
        """获取枚举值的描述"""
        descriptions = {
            1: "本专科毕业论文，支持多种学科领域",
            2: "学术期刊投稿论文，注重研究方法和数据分析",
            3: "实习工作总结报告，侧重实践经历和工作总结",
            4: "社会调查或市场调查报告，包含调查方法和结论建议"
        }
        return descriptions.get(value, "")


class MaterialType(IntEnum):
    """材料类型"""
    OUTLINE = 1  # 文章大纲（引言，主体，结论）
    REFERENCES = 2  # 中英文参考文献
    ABSTRACT = 3  # 中英文摘要
    ACKNOWLEDGEMENT = 4  # 致谢模板
    SECTION = 5  # 章节内容
    FIGURE = 6  # 图
    TABLE = 7  # 表格
    FORMULA = 8  # 公式
    CODE = 9  # 代码

    @classmethod
    def get_value_by_name(cls, name: str) -> int:
        """根据名称获取枚举值

        支持两种方式：
        1. 英文名称（如 'REFERENCES', 'OUTLINE'）
        2. 中文名称（如 '参考文献', '摘要'）
        """
        name = name.strip()
        if not name:
            return 1

        # 尝试英文名称（枚举成员名）
        try:
            return cls[name.upper()].value
        except KeyError:
            pass

        # 中文名称映射
        names = {
            "引言": 1,
            "结论": 1,
            "参考文献": 2,
            "摘要": 3,
            "致谢": 4
        }
        return names.get(name, 1)


class PaperMaterials(BaseModel):
    """论文材料清单"""
    document_id: str  # 论文ID
    type: MaterialType  # 材料类型
    labels: List[str] = []  # 材料标签
    count: Optional[int] = None  # 数量


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
    sections: List[SectionInfo] = []
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
    project_id: str | None = Field(default=None, description="项目ID，用于关联项目模板。")
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
    project_id: str | None = Field(default=None, description="项目ID，用于关联项目模板。")
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
