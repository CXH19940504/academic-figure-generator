from datetime import datetime
from enum import IntEnum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


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
    template_id: Optional[int] = None  # 排版模板ID
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
    template_id: Optional[int] = None  # 排版模板ID
